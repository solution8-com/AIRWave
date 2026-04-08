"""Adapter layer that reuses AIRWave's native Python modules."""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .errors import AIRWaveMcpError


VALID_SOURCES = {"github", "hackernews", "rss", "reddit", "telegram"}
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass
class AIRWaveRuntime:
    """Loaded runtime references from a AIRWave codebase."""

    airwave_path: Path
    ContentItem: Any
    Config: Any
    StorageManager: Any
    AIRWaveOrchestrator: Any
    create_ai_client: Any
    ContentAnalyzer: Any
    ContentEnricher: Any
    DailySummarizer: Any


def resolve_airwave_path(explicit: str | None = None) -> Path:
    """Resolve AIRWave repository path by explicit arg/env/common locations."""

    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())

    env_path = os.getenv("AIRWAVE_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    repo_root = Path(__file__).resolve().parents[2]
    cwd = Path.cwd()
    candidates.extend(
        [
            repo_root,
            cwd,
            cwd / "AIRWave",
            cwd.parent / "AIRWave",
        ]
    )

    seen: set[Path] = set()
    for candidate in candidates:
        path = candidate.resolve()
        if path in seen:
            continue
        seen.add(path)
        if _is_airwave_repo(path):
            return path

    checked = ", ".join(str(p.resolve()) for p in candidates)
    raise AIRWaveMcpError(
        code="HZ_AIRWAVE_NOT_FOUND",
        message="AIRWave repository was not found. Pass airwave_path or set AIRWAVE_PATH.",
        details={"checked": checked},
    )


def resolve_config_path(airwave_path: Path, config_path: str | None = None) -> Path:
    """Resolve config path, defaulting to <airwave>/data/config.json."""

    if not config_path:
        path = (airwave_path / "data/config.json").resolve()
    else:
        raw = Path(config_path).expanduser()
        if raw.is_absolute():
            path = raw.resolve()
        else:
            candidate = (airwave_path / raw).resolve()
            path = candidate if candidate.exists() else (Path.cwd() / raw).resolve()

    if not path.exists():
        raise AIRWaveMcpError(
            code="HZ_CONFIG_NOT_FOUND",
            message="Config file does not exist.",
            details={"config_path": str(path)},
        )

    return path


def load_runtime(airwave_path: Path) -> AIRWaveRuntime:
    """Load AIRWave modules dynamically from local repository path."""

    if not _is_airwave_repo(airwave_path):
        raise AIRWaveMcpError(
            code="HZ_INVALID_AIRWAVE_PATH",
            message="airwave_path is not a valid AIRWave repository.",
            details={"airwave_path": str(airwave_path)},
        )

    load_dotenv(airwave_path / ".env", override=False)
    _load_mcp_secrets(airwave_path, override=False)

    airwave_path_str = str(airwave_path)
    if airwave_path_str not in sys.path:
        sys.path.insert(0, airwave_path_str)

    try:
        models = importlib.import_module("src.models")
        storage = importlib.import_module("src.storage.manager")
        orchestrator = importlib.import_module("src.orchestrator")
        ai_client = importlib.import_module("src.ai.client")
        analyzer = importlib.import_module("src.ai.analyzer")
        enricher = importlib.import_module("src.ai.enricher")
        summarizer = importlib.import_module("src.ai.summarizer")
    except Exception as exc:  # pragma: no cover - import failure edge case
        raise AIRWaveMcpError(
            code="HZ_IMPORT_FAILED",
            message="Failed to load AIRWave modules.",
            details={"error": str(exc)},
        ) from exc

    return AIRWaveRuntime(
        airwave_path=airwave_path,
        ContentItem=models.ContentItem,
        Config=models.Config,
        StorageManager=storage.StorageManager,
        AIRWaveOrchestrator=orchestrator.AIRWaveOrchestrator,
        create_ai_client=ai_client.create_ai_client,
        ContentAnalyzer=analyzer.ContentAnalyzer,
        ContentEnricher=enricher.ContentEnricher,
        DailySummarizer=summarizer.DailySummarizer,
    )


def load_config(runtime: AIRWaveRuntime, config_path: Path) -> Any:
    """Load AIRWave config using native pydantic model."""

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        return runtime.Config.model_validate(payload)
    except Exception as exc:
        raise AIRWaveMcpError(
            code="HZ_CONFIG_INVALID",
            message="Failed to parse config file.",
            details={"config_path": str(config_path), "error": str(exc)},
        ) from exc


def make_storage(runtime: AIRWaveRuntime, config_path: Path) -> Any:
    """Build AIRWave storage manager bound to config's data directory."""

    data_dir = str(config_path.parent.resolve())
    return runtime.StorageManager(data_dir=data_dir)


def make_orchestrator(runtime: AIRWaveRuntime, config: Any, storage: Any) -> Any:
    """Build native AIRWave orchestrator."""

    return runtime.AIRWaveOrchestrator(config, storage)


def apply_source_filter(config: Any, sources: list[str] | None) -> tuple[Any, list[str], list[str]]:
    """Return filtered config and source selection diagnostics."""

    if not sources:
        enabled = get_enabled_sources(config)
        return config, enabled, []

    wanted = {s.strip().lower() for s in sources if s.strip()}
    unknown = sorted(wanted - VALID_SOURCES)
    chosen = sorted(wanted & VALID_SOURCES)

    clone = config.model_copy(deep=True)

    if "github" not in wanted:
        clone.sources.github = []
    if "hackernews" not in wanted:
        clone.sources.hackernews.enabled = False
    if "rss" not in wanted:
        clone.sources.rss = []
    if "reddit" not in wanted:
        clone.sources.reddit.enabled = False
        clone.sources.reddit.subreddits = []
        clone.sources.reddit.users = []
    if "telegram" not in wanted:
        clone.sources.telegram.enabled = False
        clone.sources.telegram.channels = []

    return clone, chosen, unknown


def get_enabled_sources(config: Any) -> list[str]:
    """List enabled top-level source types in effective config."""

    enabled: list[str] = []
    if getattr(config.sources, "github", None):
        enabled.append("github")
    if getattr(config.sources.hackernews, "enabled", False):
        enabled.append("hackernews")
    if getattr(config.sources, "rss", None):
        enabled.append("rss")
    if getattr(config.sources.reddit, "enabled", False):
        enabled.append("reddit")
    if getattr(config.sources.telegram, "enabled", False):
        enabled.append("telegram")
    return enabled


def items_to_dicts(items: list[Any]) -> list[dict[str, Any]]:
    """Serialize AIRWave ContentItem models."""

    return [item.model_dump(mode="json") for item in items]


def dicts_to_items(runtime: AIRWaveRuntime, payload: list[dict[str, Any]]) -> list[Any]:
    """Deserialize ContentItem list."""

    return [runtime.ContentItem.model_validate(item) for item in payload]


def get_source_counts(items: list[Any]) -> dict[str, int]:
    """Count items by source type."""

    counts: dict[str, int] = {}
    for item in items:
        key = item.source_type.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _is_airwave_repo(path: Path) -> bool:
    return (path / "src" / "main.py").exists() and (path / "pyproject.toml").exists()


def _load_mcp_secrets(airwave_path: Path, override: bool = False) -> None:
    """Load MCP secrets from JSON and inject string environment variables."""

    secrets_path = _resolve_secrets_path(airwave_path)
    if not secrets_path:
        return

    try:
        payload = json.loads(secrets_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AIRWaveMcpError(
            code="HZ_SECRETS_INVALID",
            message="Failed to parse MCP secrets file.",
            details={"secrets_path": str(secrets_path), "error": str(exc)},
        ) from exc

    if not isinstance(payload, dict):
        raise AIRWaveMcpError(
            code="HZ_SECRETS_INVALID",
            message="MCP secrets file must be a JSON object.",
            details={"secrets_path": str(secrets_path)},
        )

    env_payload = payload.get("env", payload)
    if not isinstance(env_payload, dict):
        raise AIRWaveMcpError(
            code="HZ_SECRETS_INVALID",
            message="The env field in MCP secrets must be a JSON object.",
            details={"secrets_path": str(secrets_path)},
        )

    for key, value in env_payload.items():
        if not ENV_KEY_RE.fullmatch(str(key)):
            continue
        if not isinstance(value, str):
            raise AIRWaveMcpError(
                code="HZ_SECRETS_INVALID",
                message=f"MCP secret {key} must be a string.",
                details={"secrets_path": str(secrets_path), "key": key},
            )
        if value.strip() == "":
            continue
        if override or not os.getenv(key):
            os.environ[key] = value


def _resolve_secrets_path(airwave_path: Path) -> Path | None:
    """Resolve secrets config path via env and common locations."""

    explicit = os.getenv("AIRWAVE_MCP_SECRETS_PATH")
    if explicit:
        explicit_path = Path(explicit).expanduser().resolve()
        if explicit_path.exists():
            return explicit_path
        raise AIRWaveMcpError(
            code="HZ_SECRETS_NOT_FOUND",
            message="AIRWAVE_MCP_SECRETS_PATH points to a missing file.",
            details={"secrets_path": str(explicit_path)},
        )

    cwd = Path.cwd()
    candidates = [
        cwd / ".cursor" / "mcp.secrets.json",
        cwd / ".cursor" / "mcp.secrets.local.json",
        cwd / "config" / "mcp.secrets.json",
        cwd / "config" / "mcp.secrets.local.json",
        airwave_path / "data" / "mcp.secrets.json",
        airwave_path / "data" / "mcp-secrets.json",
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return None
