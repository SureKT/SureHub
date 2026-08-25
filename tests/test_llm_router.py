from app.services import llm_router


class _FakeMsg:
    content = "hi there"


class _FakeChoice:
    message = _FakeMsg()


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 3


class _FakeResp:
    model = "claude-haiku-4-5"
    choices = [_FakeChoice()]
    usage = _FakeUsage()


def test_complete_happy_path(monkeypatch):
    monkeypatch.setattr(llm_router.litellm, "completion", lambda **k: _FakeResp())
    monkeypatch.setattr(llm_router.litellm, "completion_cost", lambda **k: 0.0001)

    r = llm_router.complete(
        messages=[{"role": "user", "content": "x"}],
        tier="local_ok",
        max_tokens=128,
    )

    assert r.text == "hi there"
    assert r.input_tokens == 10
    assert r.output_tokens == 3
    assert r.cost_usd == 0.0001
    assert r.fell_back is False
    assert r.model_served == "claude-haiku-4-5"


def test_dated_snapshot_is_not_a_fallback(monkeypatch):
    # Anthropic resolves the alias to a dated snapshot; that is not a fallback.
    class _Snap(_FakeResp):
        model = "claude-haiku-4-5-20251001"

    monkeypatch.setattr(llm_router.litellm, "completion", lambda **k: _Snap())
    monkeypatch.setattr(llm_router.litellm, "completion_cost", lambda **k: 0.0)

    r = llm_router.complete(
        messages=[{"role": "user", "content": "x"}],
        tier="local_ok",
        max_tokens=128,
    )
    assert r.fell_back is False
    assert r.model_served == "claude-haiku-4-5-20251001"


def test_real_fallback_is_detected(monkeypatch):
    class _Other(_FakeResp):
        model = "claude-sonnet-4-6"

    monkeypatch.setattr(llm_router.litellm, "completion", lambda **k: _Other())
    monkeypatch.setattr(llm_router.litellm, "completion_cost", lambda **k: 0.0)

    r = llm_router.complete(
        messages=[{"role": "user", "content": "x"}],
        tier="local_ok",
        max_tokens=128,
    )
    assert r.fell_back is True


def test_complete_cost_failure_defaults_to_zero(monkeypatch):
    def _boom(**k):
        raise RuntimeError("no pricing")

    monkeypatch.setattr(llm_router.litellm, "completion", lambda **k: _FakeResp())
    monkeypatch.setattr(llm_router.litellm, "completion_cost", _boom)

    r = llm_router.complete(
        messages=[{"role": "user", "content": "x"}],
        tier="local_ok",
        max_tokens=128,
    )
    assert r.cost_usd == 0.0


def test_local_tier_prefers_ollama_when_configured(monkeypatch):
    monkeypatch.setattr(llm_router.settings, "OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setattr(llm_router.settings, "OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setattr(llm_router.settings, "TAG_MODEL", "claude-haiku-4-5")

    assert llm_router._local_ok_models() == [
        "ollama_chat/qwen2.5:3b",
        "anthropic/claude-haiku-4-5",
    ]


def test_local_tier_is_cloud_only_without_base_url(monkeypatch):
    monkeypatch.setattr(llm_router.settings, "OLLAMA_BASE_URL", "")
    monkeypatch.setattr(llm_router.settings, "TAG_MODEL", "claude-haiku-4-5")

    assert llm_router._local_ok_models() == ["anthropic/claude-haiku-4-5"]


def test_ollama_call_gets_base_url_and_timeout_but_cloud_does_not(monkeypatch):
    monkeypatch.setattr(llm_router.settings, "OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setattr(llm_router.settings, "LLM_LOCAL_TIMEOUT", 7.0)

    assert llm_router._kwargs_for("ollama_chat/qwen2.5:3b") == {
        "api_base": "http://ollama:11434",
        "timeout": 7.0,
    }
    assert llm_router._kwargs_for("anthropic/claude-haiku-4-5") == {}


def test_local_failure_falls_back_to_cloud_without_local_kwargs(monkeypatch):
    """A dead Ollama must degrade to Haiku — and the Anthropic retry must not
    inherit the local api_base, or the fallback would fail too."""
    monkeypatch.setattr(llm_router.settings, "OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setattr(
        llm_router,
        "TIERS",
        {"local_ok": ["ollama_chat/qwen2.5:3b", "anthropic/claude-haiku-4-5"]},
    )
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if kwargs["model"].startswith("ollama"):
            raise RuntimeError("connection refused")
        return _FakeResp()

    monkeypatch.setattr(llm_router.litellm, "completion", fake_completion)
    monkeypatch.setattr(llm_router.litellm, "completion_cost", lambda **k: 0.0)

    r = llm_router.complete(
        messages=[{"role": "user", "content": "x"}],
        tier="local_ok",
        max_tokens=128,
    )

    assert r.model_served == "claude-haiku-4-5"
    assert r.fell_back is True
    assert len(calls) == 2
    assert "api_base" not in calls[1]


def test_all_models_failing_raises_last_error(monkeypatch):
    monkeypatch.setattr(
        llm_router,
        "TIERS",
        {"local_ok": ["ollama_chat/qwen2.5:3b", "anthropic/claude-haiku-4-5"]},
    )

    def boom(**kwargs):
        raise RuntimeError(f"down: {kwargs['model']}")

    monkeypatch.setattr(llm_router.litellm, "completion", boom)

    import pytest

    with pytest.raises(RuntimeError, match="anthropic"):
        llm_router.complete(
            messages=[{"role": "user", "content": "x"}],
            tier="local_ok",
            max_tokens=128,
        )
