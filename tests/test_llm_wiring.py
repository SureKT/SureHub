from app.services import llm, llm_router


def _fake_result(text):
    return llm_router.RouterResult(
        text=text,
        model_requested="anthropic/x",
        model_served="anthropic/x",
        fell_back=False,
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.0,
        latency_ms=5,
    )


def test_complete_tags_returns_router_text(monkeypatch):
    captured = {}

    def fake_complete(messages, tier, max_tokens):
        captured["tier"] = tier
        return _fake_result("tag1, tag2")

    monkeypatch.setattr(llm_router, "complete", fake_complete)
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    assert llm.complete_tags("hello note") == "tag1, tag2"
    assert captured["tier"] == "local_ok"


def test_chat_uses_cloud_tier(monkeypatch):
    captured = {}

    def fake_complete(messages, tier, max_tokens):
        captured["tier"] = tier
        captured["messages"] = messages
        return _fake_result("respuesta")

    monkeypatch.setattr(llm_router, "complete", fake_complete)
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    out = llm.chat("hola", contexto_memoria="memo")
    assert out == "respuesta"
    assert captured["tier"] == "cloud"
    # system message carries SYSTEM_BASE + injected context
    assert captured["messages"][0]["role"] == "system"
    assert "memo" in captured["messages"][0]["content"]
