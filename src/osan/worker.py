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


def get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"coordinator request failed: {exc.code} {detail}") from exc
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise RuntimeError("coordinator response must be a JSON object")
    return payload


def submit_result(coordinator_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    base = coordinator_url.rstrip("/")
    return post_json(f"{base}/v1/results", payload, {})


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
    parser.add_argument("--task", type=Path, help="Local task JSON file. Optional with --coordinator-url.")
    parser.add_argument("--output", type=Path, help="Output file for single-run mode.")
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--coordinator-url", help="Coordinator base URL, for example http://127.0.0.1:8765.")
    parser.add_argument("--submit", action="store_true", help="Submit results to --coordinator-url after validation.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of tasks to run. Use 0 for an infinite loop.")
    parser.add_argument("--interval", type=float, default=0, help="Seconds to sleep between repeated runs.")
    parser.add_argument("--stop-after-seconds", type=float, help="Stop after this many seconds, useful with --repeat 0.")
    parser.add_argument("--max-total-cost-usd", type=float, help="Stop before total estimated cost exceeds this amount.")
    parser.add_argument("--continue-on-error", action="store_true", help="Keep looping after a task failure.")
    parser.add_argument("--error-backoff", type=float, default=30, help="Seconds to sleep after an error with --continue-on-error.")
    parser.add_argument("--provider", choices=["dry-run", "openai", "anthropic"], default="dry-run")
    parser.add_argument("--model", default="dry-run-reviewer-v1")
    parser.add_argument("--worker-id", default=os.environ.get("OSAN_WORKER_ID", "local-worker"))
    parser.add_argument("--max-cost-usd", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true", help="Alias for --provider dry-run.")
    args = parser.parse_args(argv)

    provider = "dry-run" if args.dry_run else args.provider
    model = "dry-run-reviewer-v1" if provider == "dry-run" and args.model == "dry-run-reviewer-v1" else args.model

    if args.repeat < 0:
        parser.error("--repeat must be >= 0")
    if args.interval < 0:
        parser.error("--interval must be >= 0")
    if args.error_backoff < 0:
        parser.error("--error-backoff must be >= 0")
    if args.stop_after_seconds is not None and args.stop_after_seconds <= 0:
        parser.error("--stop-after-seconds must be > 0")
    if args.max_total_cost_usd is not None and args.max_total_cost_usd < 0:
        parser.error("--max-total-cost-usd must be >= 0")
    if args.submit and not args.coordinator_url:
        parser.error("--submit requires --coordinator-url")
    if not args.task and not args.coordinator_url:
        parser.error("one of --task or --coordinator-url is required")
    if args.repeat == 1 and not args.output:
        parser.error("--output is required for single-run mode")

    iteration = 0
    successes = 0
    failures = 0
    total_cost = 0.0
    started_at = time.monotonic()
    try:
        while args.repeat == 0 or iteration < args.repeat:
            if args.stop_after_seconds is not None and time.monotonic() - started_at >= args.stop_after_seconds:
                print(f"stopping after {args.stop_after_seconds}s runtime limit", flush=True)
                break

            iteration += 1
            try:
                if args.task:
                    task = load_json(args.task)
                else:
                    task = get_json(f"{args.coordinator_url.rstrip('/')}/v1/tasks/next")

                estimated_cost = estimate_cost_usd(provider, len(build_prompt(task)))
                if (
                    args.max_total_cost_usd is not None
                    and total_cost + estimated_cost > args.max_total_cost_usd
                ):
                    print(
                        f"stopping before iteration {iteration}: estimated total cost "
                        f"${total_cost + estimated_cost:.6f} exceeds ${args.max_total_cost_usd:.6f}",
                        flush=True,
                    )
                    iteration -= 1
                    break

                worker_id = args.worker_id
                if args.repeat != 1:
                    worker_id = f"{args.worker_id}-{iteration:06d}"

                payload = run_task(task, provider, model, worker_id, args.max_cost_usd)

                if args.repeat == 1 and args.output:
                    output = args.output
                else:
                    task_id = "".join(char for char in task["task_id"] if char.isalnum() or char in "._-")
                    output = args.output_dir / f"{task_id}--{worker_id}.json"

                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                    handle.write("\n")

                if args.submit:
                    response = submit_result(args.coordinator_url, payload)
                    if not response.get("ok"):
                        raise RuntimeError(f"coordinator rejected result: {response}")
                    print(f"submitted {payload['task_id']} as {worker_id}: {response.get('path')}", flush=True)
                else:
                    print(f"wrote {output}", flush=True)

                successes += 1
                total_cost += payload["cost_estimate_usd"]
            except Exception as exc:  # noqa: BLE001 - worker loop should decide whether to keep running.
                failures += 1
                print(f"iteration {iteration} failed: {exc}", flush=True)
                if not args.continue_on_error:
                    raise
                if args.error_backoff:
                    time.sleep(args.error_backoff)

            if (args.repeat == 0 or iteration < args.repeat) and args.interval:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"stopped after {iteration} iteration(s)", flush=True)
        return 130

    if args.repeat != 1 or args.coordinator_url:
        elapsed = time.monotonic() - started_at
        print(
            f"summary: iterations={iteration} successes={successes} failures={failures} "
            f"estimated_cost_usd={total_cost:.6f} elapsed_seconds={elapsed:.3f}",
            flush=True,
        )
        if failures:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
