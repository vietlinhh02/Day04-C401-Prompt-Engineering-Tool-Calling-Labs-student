---
name: time_now
track: bonus
kind: control
provider: local
requires_env: []
inputs: [tz, fmt]
outputs: [now]
side_effect: false
requires_confirmation: false
---

Returns the current time (local or UTC).

Notes:
- Use `tz="utc"` for UTC, otherwise local time.
- Use `fmt="iso"` for ISO-8601, otherwise pass a `strftime` format string.
