from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import List
from ..audio.aligner import Utterance
from ..config import settings
from .gateway import RemoteGatewayManager

logger = logging.getLogger(__name__)


@dataclass
class StrategicHint:
    category: str  # "knowledge", "action_item", "suggestion", "hermes"
    title: str
    content: str
    source: str | None = None


class MeetingStrategist:
    """
    Watches incoming transcript utterances, checks QMD / knowledge bases,
    and queries the selected Hermes agent profile (local or remote gateway) for real-time strategic context.
    """

    def __init__(self):
        self.qmd_bin = shutil.which("qmd")
        self.gateway_mgr = RemoteGatewayManager()

    def query_hermes_agent(self, profile: str, prompt: str) -> str | None:
        return self.gateway_mgr.query_agent(profile, prompt)

    def analyze_recent(self, utterances: List[Utterance], profile: str = "main") -> List[StrategicHint]:
        if not utterances:
            return []

        recent_text = " ".join(u.text for u in utterances[-4:])
        hints: List[StrategicHint] = []

        # 1. Action item detection heuristics
        action_keywords = ["action item", "we need to", "i'll follow up", "todo", "make sure to", "assign"]
        recent_lower = recent_text.lower()
        for kw in action_keywords:
            if kw in recent_lower:
                hints.append(
                    StrategicHint(
                        category="action_item",
                        title="Potential Action Item",
                        content=f"Detected commitment trigger '{kw}' in recent conversation.",
                        source="Conversation Stream",
                    )
                )
                break

        # 2. Query Selected Hermes Profile for Strategic Commentary
        if len(recent_text.split()) >= 6:
            prompt = (
                f"You are the '{profile}' Hermes meeting strategist. Based on this conversation excerpt: "
                f"\"{recent_text}\"\n"
                f"In 1-2 brief bullet points, what key question, strategic consideration, or knowledge base reference "
                f"should the user keep in mind? Be direct, actionable, and concise."
            )
            agent_comment = self.query_hermes_agent(profile, prompt)
            if agent_comment:
                hints.append(
                    StrategicHint(
                        category="hermes",
                        title=f"Strategist Insight ({profile})",
                        content=agent_comment,
                        source=f"Hermes Profile: {profile}",
                    )
                )

        # 3. Knowledge Base Querying via QMD (if available)
        if self.qmd_bin and len(recent_text.split()) > 6:
            try:
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
                            title="Related Documentation",
                            content=first_line[:180],
                            source="QMD Docs",
                        )
                    )
            except Exception:
                pass

        return hints
