"""BYOK API worker and deterministic dry-run worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .security import assert_no_secrets
from .validator import validate_result


PROMPT_VERSION = "openseti-review-v1"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def estimate_cost_usd(provider: str, prompt_chars: int) -> float:
    if provider == "dry-run":
        return 0.0
    # Conservative placeholder until provider-specific token accounting is added.
    estimated_tokens = max(1, prompt_chars // 4)
    return round(estimated_tokens * 0.000005, 6)


def build_prompt(task: dict[str, Any]) -> str:
    return (
        "You are reviewing an open science SETI-style candidate. "
        "Return conservative JSON fields only: short_summary, classification, "
        "analysis, confidence, recommendation, evidence_refs, limitations. "
        "Do not claim alien discovery.\n\n"
        f"TASK:\n{json.dumps(task, ensure_ascii=False, indent=2)}"
    )


def dry_run_analysis(task: dict[str, Any]) -> dict[str, Any]:
    input_data = task.get("input", {})
    repeat = input_data.get("repeat_observation", {})
    detected_again = repeat.get("detected_again")
    snr = input_data.get("snr")
    frequency = input_data.get("center_frequency_mhz")

    if detected_again is False:
        classification = "likely_rfi_or_instrumental"
        recommendation = "needs_human_review"
        confidence = 0.68
    else:
        classification = "interesting_but_unconfirmed"
        recommendation = "needs_follow_up_observation"
        confidence = 0.52

    return {
        "short_summary": (
            f"Candidate near {frequency} MHz has SNR {snr}, but the demo follow-up "
            "did not reproduce it, so it should be treated conservatively."
        ),
        "classification": classification,
        "analysis": (
            "The record has an interesting narrowband frequency and measurable drift, "
            "but a single non-repeating detection is not enough for a strong SETI "
            "claim. Mundane explanations such as local radio-frequency interference, "
            "instrumental artifacts, scheduling/environment effects, or incomplete "
            "follow-up coverage should be prioritized before escalation."
        ),
        "confidence": confidence,
        "recommendation": recommendation,
        "evidence_refs": [
            "task.input.center_frequency_mhz",
            "task.input.snr",
            "task.input.repeat_observation.detected_again",
            "task.known_context",
        ],
        "limitations": [
            "No raw voltage data is included in the task.",
            "The demo task does not include a full RFI environment log.",
            "One non-repeat follow-up is not sufficient to rule out all astrophysical or instrumental explanations.",
        ],
    }


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"provider request failed: {exc.code} {detail}") from exc
    return json.loads(data)


def call_openai(task: dict[str, Any], model: str) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    prompt = build_prompt(task)
    payload = {
        "model": model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    response = post_json(
        "https://api.openai.com/v1/responses",
        payload,
        {"authorization": f"Bearer {api_key}"},
    )
    text = response.get("output_text")
    if not text:
        raise RuntimeError("OpenAI response did not include output_text")
    return json.loads(text)


def call_anthropic(task: dict[str, Any], model: str) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    prompt = build_prompt(task)
    payload = {
        "model": model,
        "max_tokens": 1200,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = post_json(
        "https://api.anthropic.com/v1/messages",
        payload,
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    blocks = response.get("content", [])
    text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    if not text:
        raise RuntimeError("Anthropic response did not include text content")
    return json.loads(text)


def normalize_model_output(output: dict[str, Any]) -> tuple[dict[str, Any], float, str, list[str], list[str]]:
    result = {
        "short_summary": str(output.get("short_summary", "")).strip(),
        "classification": output.get("classification", "insufficient_data"),
        "analysis": str(output.get("analysis", "")).strip(),
    }
    confidence = float(output.get("confidence", 0.0))
    recommendation = output.get("recommendation", "insufficient_data")
    evidence_refs = output.get("evidence_refs") or ["model_output"]
    limitations = output.get("limitations") or ["Model output did not declare limitations."]
    return result, confidence, recommendation, evidence_refs, limitations


def run_task(
    task: dict[str, Any],
    provider: str,
    model: str,
    worker_id: str,
    max_cost_usd: float,
) -> dict[str, Any]:
    started = time.monotonic()
    prompt = build_prompt(task)
    cost_estimate = estimate_cost_usd(provider, len(prompt))
    if cost_estimate > max_cost_usd:
        raise RuntimeError(f"estimated cost ${cost_estimate} exceeds budget ${max_cost_usd}")

    if provider == "dry-run":
        output = dry_run_analysis(task)
    elif provider == "openai":
        output = call_openai(task, model)
    elif provider == "anthropic":
        output = call_anthropic(task, model)
    else:
        raise ValueError(f"unsupported provider: {provider}")

    result, confidence, recommendation, evidence_refs, limitations = normalize_model_output(output)
    payload = {
        "task_id": task["task_id"],
        "worker_id": worker_id,
        "mode": "api-worker",
        "model_provider": provider,
        "model_name": model,
        "prompt_version": PROMPT_VERSION,
        "input_sha256": sha256_json(task),
        "result": result,
        "confidence": confidence,
        "recommendation": recommendation,
        "evidence_refs": evidence_refs,
        "limitations": limitations,
        "runtime_seconds": round(time.monotonic() - started, 3),
        "cost_estimate_usd": cost_estimate,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    assert_no_secrets(payload)
    validate_result(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one OSAN volunteer task.")
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["dry-run", "openai", "anthropic"], default="dry-run")
    parser.add_argument("--model", default="dry-run-reviewer-v1")
    parser.add_argument("--worker-id", default=os.environ.get("OSAN_WORKER_ID", "local-worker"))
    parser.add_argument("--max-cost-usd", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true", help="Alias for --provider dry-run.")
    args = parser.parse_args(argv)

    provider = "dry-run" if args.dry_run else args.provider
    model = "dry-run-reviewer-v1" if provider == "dry-run" and args.model == "dry-run-reviewer-v1" else args.model

    task = load_json(args.task)
    payload = run_task(task, provider, model, args.worker_id, args.max_cost_usd)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
