# Release Readiness Checklist

Use this checklist before public announcements, release tags, or claims that the
demo can keep running on a volunteer machine.

## 1. Clean Local State

```bash
git fetch origin
git status -sb
git log --oneline --decorate --max-count=5
```

Expected result:

- local branch is based on the intended `origin/main`
- no unrelated working tree changes are present

## 2. Local Test Suite

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
pytest -q
scripts/check-task-intake
scripts/validate-task-manifest
```

Expected result:

- all tests pass
- task intake scores pass for all public fixtures
- task manifest matches the current `tasks/*.json` files
- no credentials or generated result files are added to Git

## 3. Local Coordinator Smoke Test

Run the release smoke test:

```bash
. .venv/bin/activate
scripts/release-smoke --repeat 10 --task-id openseti-demo-001
```

Expected result:

- the script starts a local coordinator on an ephemeral localhost port
- 10 dry-run submissions are accepted by the coordinator
- the leaderboard shows 10 valid results for the demo task
- the task summary shows 10 results, no need for more reviews, and a consensus
  recommendation
- generated result JSON remains ignored by Git

## 4. Fresh Clone Gate

Repeat install, tests, coordinator startup, and repeated dry-run submissions from
a fresh clone:

```bash
rm -rf /tmp/openseti-release-check
git clone https://github.com/chaochaoweb3/openseti-agent-network.git /tmp/openseti-release-check
cd /tmp/openseti-release-check
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
pytest -q
scripts/release-smoke --repeat 3 --task-id openseti-demo-001
```

The smoke script binds an ephemeral localhost port by default, so it can run
alongside another local coordinator.

## 5. GitHub Checks

After pushing to `main`, verify both workflows for the pushed commit:

```bash
gh run list --repo chaochaoweb3/openseti-agent-network --limit 5
```

Expected result:

- CI is successful
- Pages is successful

## Release Rule

Do not call a change release-ready if any of these fail. Fix the failing public
path first, then rerun the checklist from the beginning.
