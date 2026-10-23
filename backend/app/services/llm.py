"""Ollama client: health check and validated JSON-schema chat calls.

Never log prompt or response contents here: they contain the candidate's CV.
"""

import logging
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..config import Settings, get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Rough chars-per-token for English prose with Qwen's tokenizer; used for the pre-call
# context check. The post-call check uses Ollama's exact prompt_eval_count.
CHARS_PER_TOKEN = 3.5
CTX_WARN_RATIO = 0.8


class LLMUnavailable(Exception):
    """The LLM could not produce a valid response (after one retry)."""


@dataclass
class LLMResult(Generic[T]):
    data: T
    duration_ms: int
    prompt_tokens: int
    output_tokens: int
    attempts: int


def inline_refs(schema: dict) -> dict:
    """Inline $defs/$ref so the schema is self-contained for Ollama's grammar converter."""
    schema = deepcopy(schema)
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


class OllamaClient:
    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self.settings = settings
        self.host = settings.ollama_host.rstrip("/")
        self.http = http or httpx.Client(timeout=httpx.Timeout(300.0, connect=5.0))

    def _warn_if_ctx_heavy(self, label: str, tokens: int, kind: str) -> None:
        limit = self.settings.llm_num_ctx
        if tokens > CTX_WARN_RATIO * limit:
            log.warning(
                "[%s] %s prompt tokens %d exceed %d%% of num_ctx=%d; output may be truncated. "
                "Raise LLM_NUM_CTX or shorten inputs.",
                label, kind, tokens, int(CTX_WARN_RATIO * 100), limit,
            )

    def _chat(self, messages: list[dict], schema: dict, temperature: float, num_predict: int) -> dict:
        resp = self.http.post(
            f"{self.host}/api/chat",
            json={
                "model": self.settings.llm_model,
                "messages": messages,
                "format": schema,
                "stream": False,
                "keep_alive": self.settings.llm_keep_alive,
                "options": {
                    "num_ctx": self.settings.llm_num_ctx,
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
            },
        )
        resp.raise_for_status()
        return resp.json()

    def chat_json(
        self,
        system: str,
        user: str,
        model: type[T],
        *,
        label: str,
        temperature: float | None = None,
        num_predict: int = 2048,
    ) -> LLMResult[T]:
        """Call Ollama with `model`'s JSON schema as the output format and validate the reply.

        On invalid output, retries once with the validation error appended. Raises
        LLMUnavailable if the second attempt also fails or Ollama is unreachable.
        """
        temperature = self.settings.llm_temperature if temperature is None else temperature
        schema = inline_refs(model.model_json_schema())
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

        est = int((len(system) + len(user)) / CHARS_PER_TOKEN)
        self._warn_if_ctx_heavy(label, est, "estimated")

        start = time.perf_counter()
        prompt_tokens = output_tokens = 0
        last_error = ""
        for attempt in (1, 2):
            try:
                body = self._chat(messages, schema, temperature, num_predict)
            except httpx.HTTPError as exc:
                log.error("[%s] Ollama request failed: %s", label, type(exc).__name__)
                raise LLMUnavailable(f"Could not reach the LLM ({type(exc).__name__}).") from exc

            prompt_tokens = body.get("prompt_eval_count", 0)
            output_tokens = body.get("eval_count", 0)
            self._warn_if_ctx_heavy(label, prompt_tokens, "actual")
            content = body.get("message", {}).get("content", "")
            try:
                data = model.model_validate_json(content)
            except ValidationError as exc:
                last_error = _short_error(exc)
                log.warning("[%s] attempt %d failed validation: %s", label, attempt, last_error)
                messages = messages[:2] + [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content":
                        f"Your previous response was invalid: {last_error}\n"
                        "Return the corrected JSON only, matching the schema exactly."},
                ]
                continue

            duration_ms = int((time.perf_counter() - start) * 1000)
            log.info(
                "[%s] ok in %d ms (attempt %d, prompt %d tok, output %d tok)",
                label, duration_ms, attempt, prompt_tokens, output_tokens,
            )
            return LLMResult(data, duration_ms, prompt_tokens, output_tokens, attempt)

        raise LLMUnavailable(f"The LLM returned invalid output twice ({last_error}).")


def _short_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


@lru_cache
def get_llm() -> OllamaClient:
    return OllamaClient(get_settings())


@dataclass
class OllamaStatus:
    ok: bool
    host: str
    model: str
    reachable: bool
    model_available: bool
    available_models: list[str]
    error: str | None = None
    fix: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _model_matches(wanted: str, installed: str) -> bool:
    # "qwen2.5:7b" == "qwen2.5:7b"; "llama3" == "llama3:latest"
    if ":" not in wanted:
        wanted = f"{wanted}:latest"
    return installed == wanted


def check_ollama(settings: Settings, client: httpx.Client | None = None) -> OllamaStatus:
    host = settings.ollama_host.rstrip("/")
    model = settings.llm_model
    own_client = client is None
    client = client or httpx.Client(timeout=3.0)
    try:
        resp = client.get(f"{host}/api/tags")
        resp.raise_for_status()
        names = [m["name"] for m in resp.json().get("models", [])]
    except (httpx.HTTPError, ValueError) as exc:
        return OllamaStatus(
            ok=False, host=host, model=model, reachable=False, model_available=False,
            available_models=[],
            error=f"Cannot reach Ollama at {host} ({type(exc).__name__}).",
            fix="Start Ollama with `ollama serve` (or open the Ollama app), "
                "or set OLLAMA_HOST in .env if it runs on another machine.",
        )
    finally:
        if own_client:
            client.close()

    available = any(_model_matches(model, n) for n in names)
    return OllamaStatus(
        ok=available, host=host, model=model, reachable=True, model_available=available,
        available_models=names,
        error=None if available else f"Model '{model}' is not pulled in Ollama.",
        fix=None if available else f"ollama pull {model}",
    )
