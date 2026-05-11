#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JSONL transcript recording for SmartJobHunter eval runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class TranscriptRecorder:
    """Record eval execution events to JSONL and keep an in-memory copy."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.events: List[Dict[str, Any]] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, **payload: Any) -> None:
        item = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            **payload,
        }
        self.events.append(item)
        if self.path:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

    @property
    def path_text(self) -> str | None:
        return str(self.path) if self.path else None
