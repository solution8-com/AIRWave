"""Storage manager for configuration and state persistence."""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from ..models import Config, StarListState

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages file-based storage for configuration and state."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.config_path = self.data_dir / "config.json"
        self.summaries_dir = self.data_dir / "summaries"
        self.star_lists_dir = self.data_dir / "star_lists"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.star_lists_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> Config:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create it based on the template in README.md"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Config.model_validate(data)

    def save_config(self, config: Config, backup: bool = True) -> Path:
        """Save configuration to config.json, optionally backing up the existing file.

        Args:
            config: The Config object to save.
            backup: If True and config.json exists, copy it to config.json.bak first.

        Returns:
            Path to the saved config file.
        """
        if backup and self.config_path.exists():
            shutil.copy2(self.config_path, self.config_path.with_suffix(".json.bak"))

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
            f.write("\n")

        return self.config_path

    def save_daily_summary(self, date: str, markdown: str, language: str = "en") -> Path:
        filename = f"airwave-{date}-{language}.md"
        filepath = self.summaries_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)

        return filepath

    def load_subscribers(self) -> list:
        """Loads the list of email subscribers."""
        subscribers_path = self.data_dir / "subscribers.json"
        if not subscribers_path.exists():
            return []

        try:
            with open(subscribers_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def add_subscriber(self, email_addr: str):
        """Adds a new subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr not in subscribers:
            subscribers.append(email_addr)
            self._save_subscribers(subscribers)

    def remove_subscriber(self, email_addr: str):
        """Removes a subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr in subscribers:
            subscribers.remove(email_addr)
            self._save_subscribers(subscribers)

    def _save_subscribers(self, subscribers: list):
        """Helper to save subscribers list."""
        subscribers_path = self.data_dir / "subscribers.json"
        with open(subscribers_path, "w", encoding="utf-8") as f:
            json.dump(subscribers, f, indent=2)

    def save_star_list_state(self, list_id: str, state: StarListState) -> Path:
        """Save star list state to a JSON file using an atomic write.

        Writes to a temporary file first, then replaces the target atomically
        via os.replace to avoid partial-write corruption.

        Args:
            list_id: Unique identifier for the star list (e.g. "stars_username")
            state: Star list state to persist

        Returns:
            Path to the saved file
        """
        safe_id = list_id.replace("/", "_")
        filepath = self.star_lists_dir / f"{safe_id}.json"
        tmp_path = self.star_lists_dir / f"{safe_id}.json.tmp"

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state.model_dump(), f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, filepath)
        return filepath

    def load_star_list_state(self, list_id: str) -> Optional[StarListState]:
        """Load a previously saved star list state.

        Returns None (with a warning) if the file is missing, unreadable, or
        contains invalid JSON/data, so callers are never exposed to I/O or
        parse errors.

        Args:
            list_id: Unique identifier for the star list

        Returns:
            StarListState if found and valid, else None
        """
        safe_id = list_id.replace("/", "_")
        filepath = self.star_lists_dir / f"{safe_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StarListState.model_validate(data)
        except (json.JSONDecodeError, OSError, Exception) as exc:
            logger.warning(
                "load_star_list_state: could not load StarListState from %s – treating as no previous state (%s: %s)",
                filepath,
                type(exc).__name__,
                exc,
            )
            return None
