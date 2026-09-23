from __future__ import annotations

import datetime
from pathlib import Path
from typing import List
from ..audio.aligner import Utterance
from ..config import settings


class MeetingScribe:
    """Formats speaker-attributed transcripts into structured Obsidian-compatible notes."""

    def __init__(self, vault_dir: Path | None = None):
        self.vault_dir = vault_dir or settings.obsidian_vault_dir

    def format_markdown(
        self,
        title: str,
        utterances: List[Utterance],
        date: datetime.datetime | None = None,
    ) -> str:
        date = date or datetime.datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        time_str = date.strftime("%H:%M")

        unique_speakers = sorted(list(set(u.speaker for u in utterances)))

        lines: list[str] = [
            "---",
            f"title: \"{title}\"",
            f"date: {date_str} {time_str}",
            "type: meeting-notes",
            "tags:",
            "  - meeting",
            "  - hermes-scribe",
            f"speakers: [{', '.join(unique_speakers)}]",
            "---",
            "",
            f"# {title}",
            "",
            f"> [!info] Meeting Metadata",
            f"> **Date**: {date_str} at {time_str}  ",
            f"> **Participants**: {', '.join(unique_speakers)}  ",
            f"> **Total Turns**: {len(utterances)}",
            "",
            "## Executive Summary",
            "- *Auto-generated meeting overview will appear here.*",
            "",
            "## Key Decisions",
            "- [ ] Review architectural consensus",
            "",
            "## Action Items",
            "- [ ] Follow up on discussed action items",
            "",
            "---",
            "",
            "## Transcript",
            "",
        ]

        for u in utterances:
            start_m, start_s = divmod(int(u.start), 60)
            timestamp = f"{start_m:02d}:{start_s:02d}"
            lines.append(f"**[{timestamp}] {u.speaker}**: {u.text}\n")

        return "\n".join(lines)

    def save_to_vault(self, title: str, markdown_content: str, folder: str = "Meetings") -> Path | None:
        if not self.vault_dir or not self.vault_dir.exists():
            return None

        target_dir = self.vault_dir / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        date_prefix = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_prefix}-{safe_title}.md"
        out_path = target_dir / filename

        out_path.write_text(markdown_content, encoding="utf-8")
        return out_path
