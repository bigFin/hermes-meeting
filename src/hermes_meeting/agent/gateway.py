from __future__ import annotations

import logging
import shlex
import subprocess
from typing import Any, Dict, List

from ..config import settings

logger = logging.getLogger(__name__)


class RemoteGatewayManager:
    """Manages connections to local Hermes profiles and remote Hermes gateways (e.g. admin@beti)."""

    def __init__(self):
        self.gateways = settings.remote_gateways

    def list_all_profiles(self) -> List[Dict[str, str]]:
        """Returns all available profiles across remote gateways and the local host."""
        results: List[Dict[str, str]] = []

        # 1. Beti / Remote Gateway profiles
        for gw_key, gw in self.gateways.items():
            profiles = gw.get("profiles", ["operations", "professional", "team", "default"])
            label = gw.get("label", gw_key)
            for p in profiles:
                display_name = f"{p.title()} [{label}]"
                if p == "operations":
                    display_name = f"Ekin (Operations) [{label}]"
                elif p == "professional":
                    display_name = f"Argi (Professional) [{label}]"
                elif p == "team":
                    display_name = f"Batu (Team) [{label}]"
                elif p == "default":
                    display_name = f"Default [{label}]"

                results.append({
                    "id": f"{gw_key}:{p}",
                    "name": display_name,
                    "gateway": gw_key,
                    "profile": p,
                    "is_remote": True,
                })

        # 2. Local profiles on this host
        local_profiles: List[str] = []
        if settings.hermes_profiles_dir.exists():
            for d in settings.hermes_profiles_dir.iterdir():
                if d.is_dir() and ((d / "config.yaml").exists() or (d / "SOUL.md").exists()):
                    local_profiles.append(d.name)
        if not local_profiles:
            local_profiles = ["main", "analyst", "briefer", "voice-chat"]
        local_profiles.sort()

        for p in local_profiles:
            results.append({
                "id": f"local:{p}",
                "name": f"{p} [Local Sika]",
                "gateway": "local",
                "profile": p,
                "is_remote": False,
            })

        return results

    def query_agent(self, profile_id: str, prompt: str) -> str | None:
        """Invokes the specified agent profile (local or remote gateway) with a prompt."""
        if ":" in profile_id:
            gateway_key, profile_name = profile_id.split(":", 1)
        else:
            gateway_key, profile_name = "local", profile_id

        # Remote Gateway execution via SSH (e.g. admin@beti)
        if gateway_key in self.gateways:
            gw = self.gateways[gateway_key]
            ssh_host = gw.get("host", "admin@beti")
            hermes_home = gw.get("hermes_home", "/home/admin/.local/state/hermes/.hermes")
            hermes_bin = gw.get("hermes_bin", "/home/admin/.local/state/hermes/hermes-agent/venv/bin/hermes")
            env_file = gw.get("env_file", "/run/secrets/rendered/hermes/env")

            # Escape prompt safely for remote shell
            escaped_prompt = shlex.quote(prompt)
            remote_cmd = (
                f"set -a && . {env_file} 2>/dev/null && set +a && "
                f"HERMES_HOME={hermes_home} {hermes_bin} chat --profile {profile_name} -Q -q {escaped_prompt}"
            )
            cmd = ["ssh", "-o", "ConnectTimeout=10", ssh_host, remote_cmd]

            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.returncode == 0 and proc.stdout.strip():
                    # Clean out session_id header if present
                    output_lines = [
                        line for line in proc.stdout.strip().splitlines()
                        if not line.startswith("session_id:") and not line.startswith("Command helper:")
                    ]
                    return "\n".join(output_lines).strip()
                logger.warning("Remote gateway query failed: %s", proc.stderr)
            except Exception as e:
                logger.error("Error connecting to remote gateway %s: %s", gateway_key, e)
            return None

        # Local profile execution
        bin_path = settings.hermes_profile_bin
        if not bin_path or not bin_path.exists():
            bin_path = settings.hermes_bin

        if not bin_path or not bin_path.exists():
            return None

        cmd = [str(bin_path)]
        if bin_path.name == "hermes-profile":
            cmd.extend([profile_name, "chat", "-Q", "-q", prompt])
        else:
            cmd.extend(["chat", "--profile", profile_name, "-Q", "-q", prompt])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception as e:
            logger.debug("Local Hermes query failed: %s", e)
        return None

    def send_to_gateway(self, gateway_key: str, message: str, subject: str = "Meeting Notes", target: str = "discord") -> bool:
        """Sends a message directly to a gateway platform (Discord/Slack/Telegram) via hermes send."""
        if gateway_key not in self.gateways:
            return False

        gw = self.gateways[gateway_key]
        ssh_host = gw.get("host", "admin@beti")
        hermes_home = gw.get("hermes_home", "/home/admin/.local/state/hermes/.hermes")
        hermes_bin = gw.get("hermes_bin", "/home/admin/.local/state/hermes/hermes-agent/venv/bin/hermes")
        env_file = gw.get("env_file", "/run/secrets/rendered/hermes/env")

        escaped_message = shlex.quote(message)
        escaped_subject = shlex.quote(subject)

        remote_cmd = (
            f"set -a && . {env_file} 2>/dev/null && set +a && "
            f"HERMES_HOME={hermes_home} {hermes_bin} send --to {target} -s {escaped_subject} {escaped_message}"
        )
        cmd = ["ssh", "-o", "ConnectTimeout=10", ssh_host, remote_cmd]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            return proc.returncode == 0
        except Exception as e:
            logger.error("Failed to send message to gateway %s: %s", gateway_key, e)
            return False
