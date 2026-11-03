"""Pick the active connector: a live org when credentials are set and the user chose it, else the demo org."""

from __future__ import annotations

from ..core import config
from .demo import DemoOrg

_state = {"mode": "demo"}
_demo = DemoOrg()
_live = None


def set_mode(mode: str) -> None:
    if mode == "live" and not config.salesforce_configured():
        raise ValueError("No Salesforce credentials in api/.env (see .env.example).")
    _state["mode"] = mode


def current():
    global _live
    if _state["mode"] == "live":
        if _live is None:
            from .salesforce import SalesforceOrg
            _live = SalesforceOrg()
        return _live
    return _demo
