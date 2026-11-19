"""Client-light tier: local probes that don't need the QUAD MCP server.

The two highest-leverage skills (``quad-detect`` / ``quad-doctor``)
get their answers from this package directly, falling back to MCP
only when SDK-specific data is requested. See plan in
``C:\\Users\\pavanr\\.claude\\plans\\radiant-seeking-kazoo.md``.
"""

from .doctor import has_failures, run_doctor
from .hardware import detect_hardware, detect_hardware_server_first, envelope_keys

__all__ = [
    "detect_hardware",
    "detect_hardware_server_first",
    "envelope_keys",
    "run_doctor",
    "has_failures",
]
