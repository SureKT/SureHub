import json
import subprocess
from types import SimpleNamespace

import pytest

from app.modules.routines import engines
from app.services import llm, llm_router


def _proc(stdout="", rc=0, stderr=""):
    return SimpleNamespace(stdout=stdout, returncode=rc, stderr=stderr)


def test_claude_code_command_is_isolated_and_read_only():
    cmd = engines.claude_code_command("hola", allowed_tools=("Read", "Glob"), model="sonnet",
                                      max_budget_usd=0.5)
    assert cmd[:3] == ["claude", "-p", "hola"]
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Glob"
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--max-budget-usd") + 1] == "0.5"
    # user hooks/plugins/MCP must not leak into routine runs
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert "--strict-mcp-config" in cmd


def test_claude_code_parses_result_and_cost(tmp_path):
    seen = {}

    def runner(cmd, **kw):
        seen.update(kw)
        return _proc(json.dumps({"result": "plan", "is_error": False, "total_cost_usd": 0.03}))

    res = engines.run_claude_code("p", cwd=str(tmp_path), runner=runner, timeout=5)
    assert res.text == "plan"
    assert res.cost_usd == pytest.approx(0.03)
    assert seen["cwd"] == str(tmp_path)
    assert seen["timeout"] == 5


def test_claude_code_error_flag_raises():
    runner = lambda cmd, **kw: _proc(json.dumps({"result": "boom", "is_error": True}), rc=1)
    with pytest.raises(engines.EngineError, match="boom"):
        engines.run_claude_code("p", cwd=".", runner=runner)


def test_claude_code_non_json_raises():
    runner = lambda cmd, **kw: _proc("not json", rc=1, stderr="auth failed")
    with pytest.raises(engines.EngineError, match="auth failed"):
        engines.run_claude_code("p", cwd=".", runner=runner)


def test_claude_code_timeout_raises():
    def runner(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])
    with pytest.raises(engines.EngineError, match="timeout"):
        engines.run_claude_code("p", cwd=".", runner=runner, timeout=1)


def test_claude_code_missing_cli_raises():
    def runner(cmd, **kw):
        raise FileNotFoundError("claude")
    with pytest.raises(engines.EngineError, match="no disponible"):
        engines.run_claude_code("p", cwd=".", runner=runner)


def test_litellm_engine_goes_through_router_with_cost(monkeypatch):
    captured = {}

    def fake_complete(messages, tier, max_tokens):
        captured.update(messages=messages, tier=tier)
        return llm_router.RouterResult(text="{}", model_requested="m", model_served="m-1",
                                       fell_back=False, input_tokens=1, output_tokens=1,
                                       cost_usd=0.01, latency_ms=1)

    monkeypatch.setattr(llm_router, "complete", fake_complete)
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    res = engines.run_engine("litellm", "prompt", system="sys")
    assert res.text == "{}"
    assert res.cost_usd == 0.01
    assert captured["tier"] == "cloud"
    assert captured["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["messages"][-1]["content"] == "prompt"


def test_unknown_engine_raises():
    with pytest.raises(engines.EngineError):
        engines.run_engine("nope", "p")
