# Roadmap

This roadmap keeps OpenSETI Agent Network focused on a small number of public,
auditable milestones. The project should grow as a reproducible volunteer review
network, not as a proxy for private accounts or autonomous discovery claims.

## Current Phase: Runnable Prototype

Target: July 2026.

The current priority is to keep the public demo boringly runnable.

- Keep `pytest -q` green across supported Python versions.
- Keep the GitHub Pages homepage deployed.
- Keep the local coordinator plus dry-run worker path working from a fresh clone.
- Keep task catalog, leaderboard, and per-task summary endpoints working.
- Keep the task manifest in sync with public fixture file hashes.
- Keep result validation strict enough to reject credentials, private data, and
  unsupported scientific claims.
- Document the continuous worker path clearly enough for a new volunteer to run
  it without maintainer help.

## Next Phase: Useful Task Intake

Target: August 2026.

The next priority is to move beyond a single synthetic demo while keeping task
intake conservative.

- Add a task scoring rubric for public astronomy or SETI-style review tasks.
- Add at least one additional public, redistributable task fixture.
- Track task source, license, review questions, expected output, and caveats in
  every task file.
- Add tests and validation scripts that protect task schema compatibility and
  result reproducibility.
- Make task proposals easy to triage with labels and a maintainer task template.

## Following Phase: Volunteer Confidence

Target: September 2026.

The project should make it obvious whether the network is healthy.

- Add a lightweight status page section for CI health, latest release, and demo
  coordinator workflow status.
- Add an operator checklist for release readiness.
- Add a documented fresh-clone soak test before public announcements.
- Add examples for both dry-run and BYOK provider usage without exposing
  credentials.

## Later: Network Coordination

These items are intentionally later because they expand the trust boundary.

- Signed task bundles and stronger provenance metadata.
- Multi-task queues and task assignment policy.
- Richer result aggregation policies for quorum thresholds, reviewer weighting,
  and long-running task health.
- Optional public leaderboard hygiene and abuse controls.
- More provider integrations that keep credentials local.

## Maintainer Priority Rule

When choosing work, prefer the first item that is true:

1. Fix a broken public path: clone, install, test, run worker, validate result,
   deploy homepage.
2. Improve public trust: stricter validation, clearer caveats, safer defaults,
   better source/license metadata.
3. Improve contributor flow: issue templates, roadmap clarity, task examples,
   review checklists.
4. Add capability only after the operating and safety boundaries are clear.
