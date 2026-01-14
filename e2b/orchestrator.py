"""
Auto-generated Child Agent Spawner

This module provides functions to spawn specialized child agents
in E2B sandboxes using pre-built templates.

Generated: 2026-01-14T14:31:27.292268Z
"""

from __future__ import annotations

from typing import Dict, List, Optional

try:
    from e2b import Sandbox
except ImportError as exc:  # pragma: no cover - optional runtime dependency
    Sandbox = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

TEMPLATE_IDS: Dict[str, str] = {
  "foundation": "pending-foundation",
  "steel_fabrication": "pending-steel_fabrication",
  "lumber_mill": "pending-lumber_mill",
  "trades_contractor": "pending-trades_contractor",
  "general_contractor": "pending-general_contractor",
  "metal_fabrication": "pending-metal_fabrication",
  "equipment_rental": "pending-equipment_rental",
  "professional_services": "pending-professional_services"
}


class TemplateNotDeployedError(RuntimeError):
    """Raised when a template has not been deployed to E2B."""


def _require_sdk() -> None:
    if Sandbox is None:  # pragma: no cover
        raise ImportError(
            "Install the E2B Python SDK: pip install e2b"
        ) from _IMPORT_ERROR


def spawn_child_agent(
    profile: str,
    task: str,
    timeout_minutes: int = 10,
) -> Dict[str, object]:
    _require_sdk()
    template_id = TEMPLATE_IDS.get(profile)
    if not template_id or template_id.startswith("pending-"):
        raise TemplateNotDeployedError(f"Template not deployed for profile: {profile}")

    timeout_seconds = timeout_minutes * 60

    sandbox = Sandbox.create(template=template_id, timeout=timeout_seconds)
    try:
        escaped_task = task.replace('"', '\"')
        result = sandbox.commands.run(
            f'claude-code --print "{escaped_task}"',
            timeout=timeout_seconds,
        )
        return {
            "sandbox_id": getattr(sandbox, "sandbox_id", None),
            "profile": profile,
            "result": getattr(result, "stdout", ""),
            "exit_code": getattr(result, "exit_code", 0),
        }
    finally:
        sandbox.close()


def list_profiles() -> List[str]:
    return list(TEMPLATE_IDS.keys())
