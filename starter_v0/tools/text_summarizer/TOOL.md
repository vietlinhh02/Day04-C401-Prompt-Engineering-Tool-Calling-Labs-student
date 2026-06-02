---
name: text_summarizer
track: bonus
kind: local_formatter
provider: local
requires_env: []
inputs: [text, max_sentences, max_chars]
outputs: [summary]
side_effect: false
requires_confirmation: false
---

Summarize raw text locally (deterministic).

Notes:
- Designed for quick “compress this paragraph” use-cases.
- Not a web fetcher; it only transforms provided text.
