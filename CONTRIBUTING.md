# Contributing

Thanks for helping with OpenSETI Agent Network.

## Ways To Contribute

- Add public science tasks under `tasks/`.
- Improve result validation and secret scanning.
- Add provider integrations that keep credentials local.
- Improve documentation for Codex, Claude Code, and BYOK workflows.
- Review demo results and propose better scientific review criteria.

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
pytest
```

## Pull Request Checklist

- Tests pass with `pytest -q`.
- No API keys, OAuth tokens, cookies, session IDs, or generated result files are
  committed.
- New result formats remain compatible with `schemas/result.schema.json`.
- Scientific language stays conservative and auditable.

## Task Contributions

Task JSON should use public or redistributable data. Include source and license
metadata whenever possible. Do not include private datasets, credentials, or
browser session data.
