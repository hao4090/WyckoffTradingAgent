from __future__ import annotations

import importlib
import sys
from types import ModuleType


class FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name

    def tool(self):
        return lambda func: func

    def run(self) -> None:
        return None


def import_mcp_server(monkeypatch):
    mcp_pkg = ModuleType("mcp")
    server_pkg = ModuleType("mcp.server")
    fastmcp_pkg = ModuleType("mcp.server.fastmcp")
    fastmcp_pkg.FastMCP = FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp", mcp_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server", server_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_pkg)
    sys.modules.pop("mcp_server", None)
    return importlib.import_module("mcp_server")


def test_run_funnel_simulation_routes_to_strategy_api(monkeypatch):
    mcp_server = import_mcp_server(monkeypatch)
    captured = {}

    def fake_screen_stocks_legacy(*, board):
        captured["board"] = board
        return {"symbols_for_report": [{"code": "000001"}], "summary": {"total_scanned": 1}}

    monkeypatch.setattr("integrations.strategy_api_client.screen_stocks_legacy", fake_screen_stocks_legacy)

    result = mcp_server.run_funnel_simulation(board="main_chinext")

    assert result["success"] is True
    assert result["source"] == "strategy_api"
    assert result["candidates"] == [{"code": "000001"}]
    assert captured == {"board": "all"}
