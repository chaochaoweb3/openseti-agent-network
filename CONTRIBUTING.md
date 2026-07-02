# Contributing

Thanks for helping with OpenSETI Agent Network.

## Ways To Contribute

- Add public science tasks under `tasks/`.
- Improve result validation and secret scanning.
- Add provider integrations that keep credentials local.
- Improve documentation for Codex, Claude Code, and BYOK workflows.
- Review demo results and propose better scientific review criteria.
- Pick a scoped item from [`ROADMAP.md`](ROADMAP.md) or the maintainer task
  issue template.

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
- Runtime changes include a coordinator or fresh-clone smoke test when relevant.

## Task Contributions

Task JSON should use public or redistributable data. Include source and license
metadata whenever possible. Do not include private datasets, credentials, or
browser session data. Before opening a task PR, check
[`docs/task-intake-rubric.md`](docs/task-intake-rubric.md) and run:

```bash
scripts/validate-task tasks/<task-id>.json
scripts/check-task-intake tasks/<task-id>.json
scripts/validate-task-manifest
pytest -q
```

## Maintainer Tasks

Maintainer-generated work should follow
[`docs/maintainer-operating-loop.md`](docs/maintainer-operating-loop.md). Keep
each task tied to one outcome, one verification path, and one roadmap phase.
Avoid broad refactors unless they unblock a broken public path or a clear safety
boundary.
