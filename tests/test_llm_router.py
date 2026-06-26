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
