# Task Intake Rubric

Use this rubric before adding a task under `tasks/` or accepting a task proposal.
The goal is to admit public, auditable astronomy or SETI-style review tasks that
volunteers can reproduce without private credentials or unsupported discovery
claims.

## Required Task Fields

Every task JSON file must include:

- `task_id`: stable lowercase identifier, unique under `tasks/`.
- `domain`: scientific domain, for example `seti` or `astronomy`.
- `task_type`: review shape, for example `candidate_review`.
- `title`: short human-readable title.
- `dataset_source`: public source name, DOI, archive, catalog, or clearly marked
  synthetic demo source.
- `source_license`: reuse terms, preferably an SPDX identifier or public-domain
  marker such as `CC0`.
- `input_uri`: local or public path to the input payload.
- `input_sha256`: checksum for external input, or `self-contained-demo` for a
  fully embedded synthetic demo.
- `objective`: what reviewers should decide or produce.
- `caveats`: known limitations and scientific caution notes.
- `input`: structured task data.
- `review_questions`: concrete questions reviewers must answer.
- `expected_outputs`: result fields expected from workers or agent clients.

## Intake Score

Score each proposal from 0 to 2 for each category.

| Category | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Source | private, missing, or unclear | public but attribution is weak | public and clearly attributed |
| License | missing or non-redistributable | ambiguous but likely usable | explicit redistributable license |
| Reproducibility | cannot be run from the task file | requires manual interpretation | self-contained or clearly linked |
| Review value | vague or toy-only | useful but narrow | scientifically useful and auditable |
| Caveats | overclaims or omits limitations | partial limitations | conservative caveats are explicit |
| Privacy | includes private data or credentials | unclear provenance | no private data or credentials |

Accept tasks scoring at least 10 out of 12 with no hard rejection criteria.

## Hard Rejection Criteria

Reject or rewrite a task if any item is true:

- It includes API keys, OAuth tokens, cookies, session IDs, browser profile
  paths, private file paths, or private datasets.
- It requires a volunteer to share account access or hosted credentials.
- The source cannot be redistributed or cited.
- The task invites a claim of confirmed extraterrestrial life, alien discovery,
  or any other unsupported scientific conclusion.
- Review questions cannot be answered from the task data and public references.
- Caveats are missing for noisy, synthetic, incomplete, or preliminary data.

## Scientific Review Questions

A good task asks questions like:

- What evidence is present in the candidate record?
- What ordinary RFI, instrument, scheduling, catalog, or data-quality
  explanations remain plausible?
- What evidence is missing before escalation?
- Should the reviewer recommend rejection, human review, follow-up observation,
  or insufficient data?

Avoid questions that ask the model to declare discovery or infer unavailable raw
data.

## Acceptance Checklist

- [ ] `scripts/validate-task tasks/<task-id>.json` passes.
- [ ] `pytest -q` passes if schema, validation, or worker behavior changed.
- [ ] The task has source and license metadata.
- [ ] The task includes caveats and conservative review questions.
- [ ] The task contains no credentials, private data, or generated results.
- [ ] The task output can be validated against `schemas/result.schema.json`.

