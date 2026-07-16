#!/usr/bin/env python3
"""Compatibility entry point for the current Apple Silicon release builder.

The former implementation referenced an obsolete, mojibake directory layout.
Keep this filename for existing documentation and scripts, but delegate all
work to the single source-of-truth builder under ``Build``.
"""

from __future__ import annotations

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "Build" / "build_macos_arm64_release.py"

if not BUILDER.is_file():
    raise SystemExit(f"macOS builder missing: {BUILDER}")

runpy.run_path(str(BUILDER), run_name="__main__")
