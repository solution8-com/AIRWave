#!/usr/bin/env python3
"""Local smoke check for AIRWave MCP integration."""

from __future__ import annotations

import asyncio
import json

from src.mcp.airwave_adapter import resolve_airwave_path
from src.mcp.server import hz_get_metrics
from src.mcp.service import AIRWavePipelineService


async def _main() -> None:
    airwave_path = resolve_airwave_path()
    service = AIRWavePipelineService()
    validation = await service.validate_config(
        airwave_path=str(airwave_path),
        check_env=False,
    )
    metrics = hz_get_metrics()

    payload = {
        "ok": True,
        "airwave_path": str(airwave_path),
        "config_path": validation["config_path"],
        "enabled_sources": validation["enabled_sources"],
        "languages": validation["ai"]["languages"],
        "metrics_ok": metrics["ok"],
        "metrics_tool": metrics["tool"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
