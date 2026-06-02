from __future__ import annotations

from datetime import datetime
from typing import Any

from tools._shared import err


def time_now(tz: str = "local", fmt: str = "iso") -> dict[str, Any]:
    """
    Return the current time.

    tz: "local" (default) or "utc"
    fmt: "iso" (default) or a datetime.strftime format string
    """
    try:
        now = datetime.utcnow() if (tz or "local").lower() == "utc" else datetime.now()
        if (fmt or "iso").lower() == "iso":
            rendered = now.isoformat(timespec="seconds")
        else:
            rendered = now.strftime(fmt)
        return {"tool": "time_now", "tz": tz, "fmt": fmt, "now": rendered}
    except Exception as exc:
        return err("time_now", exc)
