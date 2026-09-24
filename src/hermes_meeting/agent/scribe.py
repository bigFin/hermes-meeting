from __future__ import annotations

import datetime
import logging
import subprocess
from pathlib import Path
from typing import List
from ..audio.aligner import Utterance
from ..config import settings

logger = logging.getLogger(__name__)


class MeetingScribe:
    """Formats speaker-attributed transcripts into structured Obsidian-compatible notes."""

    def __init__(self, vault_dir: Path | None = None):
        self.vault_dir = vault_dir or settings.obsidian_vault_dir

    def generate_ai_summary(self, profile: str, utterances: List[Utterance]) -> str | None:
        bin_path = settings.hermes_profile_bin
        if not bin_path or not bin_path.exists():
            bin_path = settings.hermes_bin

        if not bin_path or not bin_path.exists() or not utterances:
            return None

        # Build transcript text for prompt
        transcript_text = "\n".join(f"{u.speaker}: {u.text}" for u in utterances)
        prompt = (
            f"You are the '{profile}' scribe. Synthesize this meeting transcript into:\n"
            f"1. Executive Summary (2-3 sentences)\n"
            f"2. Key Decisions made\n"
            f"3. Action Items (- [ ] checkbox format)\n\n"
            f"Transcript:\n{transcript_text[:4000]}"
        )

        cmd = [str(bin_path)]
        if bin_path.name == "hermes-profile":
            cmd.extend([profile, "chat", "-Q", "-q", prompt])
        else:
            cmd.extend(["chat", "-Q", "-q", prompt])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception as e:
            logger.debug("AI summary generation timed out or failed: %s", e)
        return None

    def format_markdown(
        self,
        title: str,
        utterances: List[Utterance],
        date: datetime.datetime | None = None,
        profile: str = "main",
    ) -> str:
        date = date or datetime.datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        time_str = date.strftime("%H:%M")

        unique_speakers = sorted(list(set(u.speaker for u in utterances)))
        ai_summary = self.generate_ai_summary(profile, utterances)

        lines: list[str] = [
            "---",
            f"title: \"{title}\"",
            f"date: {date_str} {time_str}",
            "type: meeting-notes",
            f"scribe_agent: {profile}",
            "tags:",
            "  - meeting",
            f"  - hermes-{profile}",
            f"speakers: [{', '.join(unique_speakers)}]",
            "---",
            "",
            f"# {title}",
            "",
            f"> [!info] Meeting Metadata",
            f"> **Date**: {date_str} at {time_str}  ",
            f"> **Participants**: {', '.join(unique_speakers)}  ",
            f"> **Scribe Profile**: `{profile}`  ",
            f"> **Total Turns**: {len(utterances)}",
            "",
        ]

        if ai_summary:
            lines.append("## Executive Synthesis\n")
            lines.append(ai_summary)
            lines.append("\n---\n")
        else:
            lines.extend([
                "## Executive Summary",
                "- *Meeting recorded and transcribed.*",
                "",
                "## Action Items",
                "- [ ] Review transcript notes",
                "",
                "---",
                "",
            ])

        lines.append("## Transcript\n")

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
