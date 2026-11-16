from app.modules.routines import engines
from app.services import llm, llm_router


def test_litellm_engine_goes_through_router_with_cost(monkeypatch):
    captured = {}

    def fake_complete(messages, tier, max_tokens):
        captured.update(messages=messages, tier=tier)
        return llm_router.RouterResult(text="{}", model_requested="m", model_served="m-1",
                                       fell_back=False, input_tokens=1, output_tokens=1,
                                       cost_usd=0.01, latency_ms=1)

    monkeypatch.setattr(llm_router, "complete", fake_complete)
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    res = engines.run_litellm("prompt", system="sys")
    assert res.text == "{}"
    assert res.cost_usd == 0.01
    assert captured["tier"] == "cloud"
    assert captured["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["messages"][-1]["content"] == "prompt"
