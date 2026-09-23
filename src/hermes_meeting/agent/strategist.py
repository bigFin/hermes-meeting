from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import List
from ..audio.aligner import Utterance


@dataclass
class StrategicHint:
    category: str  # "knowledge", "action_item", "suggestion"
    title: str
    content: str
    source: str | None = None


class MeetingStrategist:
    """
    Watches incoming transcript utterances, checks QMD / knowledge bases,
    and yields real-time strategic prompts/reminders for the meeting sidebar.
    """

    def __init__(self):
        self.qmd_bin = shutil.which("qmd")

    def analyze_recent(self, utterances: List[Utterance]) -> List[StrategicHint]:
        if not utterances:
            return []

        # Combine last 3-4 utterances
        recent_text = " ".join(u.text for u in utterances[-4:]).lower()
        hints: List[StrategicHint] = []

        # 1. Action item detection heuristics
        action_keywords = ["action item", "we need to", "i'll follow up", "todo", "make sure to", "assign"]
        for kw in action_keywords:
            if kw in recent_text:
                hints.append(
                    StrategicHint(
                        category="action_item",
                        title="Potential Action Item Detected",
                        content=f"Detected trigger '{kw}' in recent conversation.",
                        source="Conversation Stream",
                    )
                )
                break

        # 2. Knowledge Base Querying via QMD (if available)
        if self.qmd_bin and len(recent_text.split()) > 6:
            try:
                # Query docs collection with a snippet
                query_snippet = " ".join(recent_text.split()[-12:])
                proc = subprocess.run(
                    [self.qmd_bin, "query", query_snippet, "-c", "docs", "--limit", "1"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    first_line = proc.stdout.strip().splitlines()[0]
                    hints.append(
                        StrategicHint(
                            category="knowledge",
                            title="Related Knowledge Found",
                            content=first_line[:180],
                            source="QMD Docs",
                        )
                    )
            except Exception:
                pass

        return hints
