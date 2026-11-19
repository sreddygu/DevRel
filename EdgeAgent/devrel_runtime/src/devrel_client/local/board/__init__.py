"""UNO Q / QCS2210 board interaction package.

The skill ``devrel-unoq`` was historically a wall of inline ``ssh user@host
"..."`` snippets driven by Claude through Bash. This package turns those
into a typed Python surface so the skill becomes a thin caller and the
underlying ops are testable, cancellable, and consistent.

We deliberately use the OS ``ssh``/``scp``/``adb`` binaries via subprocess
rather than paramiko -- the user's SSH keys and config (~/.ssh/config,
ssh-agent) are then automatically respected and we don't add a runtime
dep.
"""

from .commands import BoardOpResult, run_command

__all__ = ["BoardOpResult", "run_command"]
