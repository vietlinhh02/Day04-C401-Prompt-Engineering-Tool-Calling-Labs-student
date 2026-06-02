---
name: weather_mock
track: bonus
kind: live_api
provider: local
requires_env: []
inputs: [city, day, units]
outputs: [forecast]
side_effect: false
requires_confirmation: false
---

Mock weather lookup for routing + arg extraction tests.

Notes:
- No network calls. Returns deterministic placeholder data.
- Supports `day`: `today` | `tomorrow`, and `units`: `C` | `F`.
