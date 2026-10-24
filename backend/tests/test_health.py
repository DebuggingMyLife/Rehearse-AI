import httpx

from app.config import Settings
from app.services.llm import check_cv_builder_llm, check_ollama


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _settings(model="qwen2.5:7b") -> Settings:
    return Settings(_env_file=None, llm_model=model, ollama_host="http://ollama:11434")


def test_model_available():
    c = _client(lambda r: httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
    s = check_ollama(_settings(), c)
    assert s.ok and s.model_available and s.fix is None


def test_model_missing_gives_pull_command():
    c = _client(lambda r: httpx.Response(200, json={"models": [{"name": "qwen2.5:0.5b"}]}))
    s = check_ollama(_settings(), c)
    assert s.reachable and not s.ok
    assert s.fix == "ollama pull qwen2.5:7b"


def test_latest_tag_matches_untagged_name():
    c = _client(lambda r: httpx.Response(200, json={"models": [{"name": "llama3:latest"}]}))
    assert check_ollama(_settings("llama3"), c).ok


def test_unreachable():
    def boom(r):
        raise httpx.ConnectError("refused")

    s = check_ollama(_settings(), _client(boom))
    assert not s.reachable and not s.ok
    assert "ollama serve" in s.fix


def test_cv_builder_checks_its_own_model():
    c = _client(lambda r: httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
    s = check_cv_builder_llm(_settings(), c)  # default CV Builder model is gpt-oss:20b
    assert not s.ok and s.backend == "local" and s.fix == "ollama pull gpt-oss:20b"
    c = _client(lambda r: httpx.Response(200, json={"models": [{"name": "gpt-oss:20b"}]}))
    assert check_cv_builder_llm(_settings(), c).ok


def test_cv_builder_groq_needs_a_key():
    s = Settings(_env_file=None, cv_builder_llm_backend="groq", groq_api_key=None)
    status = check_cv_builder_llm(s)
    assert not status.ok and "GROQ_API_KEY" in status.error
    assert check_cv_builder_llm(Settings(_env_file=None, cv_builder_llm_backend="groq", groq_api_key="k")).ok
