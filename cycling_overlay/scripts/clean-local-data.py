#!/usr/bin/env python3
"""Remove local data and caches before committing or pushing.

This ensures no personal credentials, saved devices, or cached bytecode
accidentally ends up in the repository.

Usage:
    python scripts/clean-local-data.py [--backup]

The --backup flag creates a timestamped copy of the local config before
removing it (saved to the Desktop or home directory).
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "cycling-overlay"
REPO_ROOT = Path(__file__).resolve().parent.parent / "cycling_overlay"


def _config_dir() -> Path | None:
    """Return the platform-specific local config directory for the app."""
    system = platform.system()
    if system == "Windows":
        appdata = Path.home() / "AppData" / "Roaming"
        if not appdata.exists():
            appdata = Path.home() / "AppData" / "Local"
        candidate = appdata / APP_NAME
    elif system == "Darwin":
        candidate = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        # Linux / *BSD
        xdg_config = Path.home() / ".config"
        candidate = xdg_config / APP_NAME
    return candidate if candidate.exists() else None


def _backup_dir() -> Path:
    """Choose a safe place for backups."""
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop
    return Path.home()


def remove_local_config(backup: bool = False) -> None:
    """Remove the platform-specific app config directory."""
    cfg_dir = _config_dir()
    if cfg_dir is None:
        print("[clean] No local config directory found (already clean).")
        return

    if backup:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = _backup_dir() / f"{APP_NAME}_config_backup_{timestamp}"
        shutil.copytree(cfg_dir, backup_path, dirs_exist_ok=True)
        print(f"[clean] Config backed up to: {backup_path}")

    shutil.rmtree(cfg_dir, ignore_errors=True)
    print(f"[clean] Removed local config: {cfg_dir}")


def remove_project_caches() -> None:
    """Remove __pycache__ and *.pyc inside the repository."""
    removed = 0
    for pyc in REPO_ROOT.rglob("__pycache__"):
        if pyc.is_dir():
            shutil.rmtree(pyc, ignore_errors=True)
            removed += 1
    for pyc in REPO_ROOT.rglob("*.pyc"):
        if pyc.is_file():
            pyc.unlink(missing_ok=True)
            removed += 1
    if removed:
        print(f"[clean] Removed {removed} cache artifact(s) from project.")
    else:
        print("[clean] No cache artifacts found in project.")


def remove_stray_configs() -> None:
    """Remove any config.json that might have been copied into the repo."""
    stray = list(REPO_ROOT.rglob("config.json")) + list(REPO_ROOT.rglob("*.local.json"))
    removed = 0
    for path in stray:
        if path.is_file():
            path.unlink(missing_ok=True)
            print(f"[clean] Removed stray config file: {path}")
            removed += 1
    if not removed:
        print("[clean] No stray config files inside the project.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean local app data and caches before pushing to GitHub."
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup the local config before removing it.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Cycling Overlay — Clean Local Data")
    print("=" * 60)

    remove_local_config(backup=args.backup)
    remove_project_caches()
    remove_stray_configs()

    print("-" * 60)
    print("Done. You can now safely commit and push.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
