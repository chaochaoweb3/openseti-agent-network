# Open Science Agent Network Agent Rules

You are participating in an open science volunteer task from the user's local
machine. Follow these rules exactly.

## Safety

- Do not upload, print, summarize, or infer secrets.
- Do not include API keys, OAuth tokens, cookies, session IDs, authorization
  headers, browser profile paths, or local private file contents in result JSON.
- Do not automate ChatGPT, Claude, or other web subscriptions as a remote proxy.
- Do not claim discovery of extraterrestrial life. Phrase conclusions as review
  judgments over public data.

## Task Flow

1. Inspect `tasks/*.json` and choose one uncompleted task.
2. Read the task's `objective`, `input`, `review_questions`, and
   `expected_outputs`.
3. Produce a result JSON matching `schemas/result.schema.json`.
4. Include evidence references, uncertainty, and a conservative review decision.
5. Run `scripts/validate-result <result.json>`.
6. Leave final submission under explicit user control.

## Result Expectations

- Use `model_provider` as `agent-client` unless the user explicitly chooses
  another local provider.
- Use `model_name` as the visible client/model name if known, otherwise
  `unknown-agent`.
- Use `confidence` between `0.0` and `1.0`.
- Use `recommendation` as one of:
  - `reject_likely_rfi`
  - `needs_human_review`
  - `needs_follow_up_observation`
  - `insufficient_data`
- Keep `evidence_refs` tied to task fields, public URLs, or generated artifacts.
