---
name: Maintainer task
about: Track a concrete maintenance or roadmap item
title: "[Maintainer]: "
labels: maintainer-task
---

## Outcome

What should be true when this is done?

## Why now?

Which roadmap phase or public path does this support?

## Proposed steps

- [ ] 

## Verification

- [ ] `pytest -q`
- [ ] Fresh-clone or coordinator smoke test, if this affects runtime behavior
- [ ] GitHub Actions checked after merge, if this changes `main`

## Safety boundary

- [ ] No credentials, cookies, tokens, private data, or generated result files
      are committed.
- [ ] Scientific language remains conservative and auditable.
