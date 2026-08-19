# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""🖥️ Dashboard — FastAPI + Streamlit UI.

A small web layer to browse remembered Events, ask questions, and get the
daily summary. FastAPI serves the JSON API; a Streamlit app (added later)
consumes it. ``fastapi`` is imported lazily inside :func:`create_app` so the
package imports without the ``dashboard`` extra.
"""

from __future__ import annotations

from aura.dashboard.api import create_app

__all__ = ["create_app"]
