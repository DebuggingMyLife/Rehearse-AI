import httpx

from app.config import Settings
from app.services.llm import check_ollama


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
