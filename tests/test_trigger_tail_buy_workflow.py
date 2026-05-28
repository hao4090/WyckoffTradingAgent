from __future__ import annotations

import json


class _FakeResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_api_dispatch_defaults_to_current_repository(monkeypatch) -> None:
    from scripts import trigger_tail_buy_workflow as mod

    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("TAIL_BUY_WORKFLOW_REPO", raising=False)
    captured = _capture_dispatch_request(monkeypatch, mod)

    assert mod._dispatch_with_api("token", "main") == 0
    assert captured["url"] == (
        "https://api.github.com/repos/YoungCan-Wang/Wyckoff-Analysis/actions/workflows/"
        "tail_buy_1420.yml/dispatches"
    )
    assert captured["body"] == {"ref": "main"}


def test_api_dispatch_allows_explicit_repository_override(monkeypatch) -> None:
    from scripts import trigger_tail_buy_workflow as mod

    monkeypatch.setenv("GITHUB_REPOSITORY", "wrong/repo")
    monkeypatch.setenv("TAIL_BUY_WORKFLOW_REPO", "owner/custom")
    captured = _capture_dispatch_request(monkeypatch, mod)

    assert mod._dispatch_with_api("token", "release") == 0
    assert captured["url"] == (
        "https://api.github.com/repos/owner/custom/actions/workflows/tail_buy_1420.yml/dispatches"
    )
    assert captured["body"] == {"ref": "release"}


def _capture_dispatch_request(monkeypatch, mod) -> dict:
    captured: dict = {}

    def fake_urlopen(req, timeout: int):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    return captured
