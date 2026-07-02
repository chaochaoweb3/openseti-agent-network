# Maintainer Operating Loop

This document defines how a maintainer agent should keep this repository moving
without turning into a one-shot command runner.

## Loop

Each maintenance run should follow the same order:

1. Refresh live state.
   - `git fetch origin`
   - `git status -sb`
   - GitHub Actions status for the latest `main`
   - open issues and pull requests
2. Classify work.
   - Broken public path: CI, Pages, install, worker run, validation
   - Trust and safety: secret scanning, schema validation, conservative claims
   - Contributor flow: task intake, templates, documentation
   - Capability growth: new providers, queue behavior, aggregation
3. Pick one primary outcome.
   - Prefer a small change that can be verified and shipped in the same run.
   - Do not mix unrelated cleanup with roadmap or runtime changes.
4. Verify.
   - Run `pytest -q` for code or documentation examples that touch commands.
   - For runtime confidence, verify from a fresh clone before claiming release
     readiness.
   - Check GitHub Actions after pushing to `main`.
5. Leave state.
   - Summarize what changed, what passed, what remains blocked, and the next
     highest-value task.

## Decision Rules

- Do not automate account sharing, browser subscriptions, cookies, or hosted
  credential pooling.
- Do not claim extraterrestrial discovery from demo outputs.
- Do not open broad refactor PRs when a narrow public-path fix is available.
- Do not comment on GitHub just to appear active; comment only when a maintainer
  requested action, a blocker was removed, or a concrete test result matters.
- Treat stale local checkouts as disposable. Live GitHub state is authoritative.

## Default Commands

```bash
git fetch origin
git status -sb
. .venv/bin/activate
pytest -q
scripts/check-task-intake
scripts/validate-task-manifest
python -m osan.server --host 127.0.0.1 --port 8765
scripts/run-task --task tasks/openseti-demo-001.json --coordinator-url http://127.0.0.1:8765 --submit --repeat 10 --interval 0 --dry-run --worker-id maintainer-smoke
curl http://127.0.0.1:8765/v1/leaderboard
curl http://127.0.0.1:8765/v1/tasks/openseti-demo-001/summary
```

For a release-confidence run, repeat the install and smoke test from a fresh
clone under `/tmp`. Use [`release-readiness.md`](release-readiness.md) as the
full checklist.

## Status Format

Every run should end with this compact state:

```text
Moved:
- ...

Verified:
- ...

Blocked:
- ...

Next:
- ...
```
