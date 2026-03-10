#!/usr/bin/env python3
"""Compare a vLLM-hosted judge (Qwen3-Next-80B) against the existing 3-judge panel.

Loads aggregate JSONL files that already contain judge_1/2/3 scores, runs the vLLM
model as a 4th judge using the same no-hint prompts, and computes pairwise agreement
rates and Krippendorff's alpha.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# ── Imports from the benchmark module ────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openrouter_benchmark import (
    DEFAULT_JUDGE_SYSTEM_PROMPT_NO_HINT,
    DEFAULT_JUDGE_USER_TEMPLATE_NO_HINT,
    find_first_json_object,
    krippendorff_alpha_ordinal,
    parse_judge_output,
)

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_VLLM_URL = "http://smeagols-lair:19000/v1/chat/completions"
DEFAULT_VLLM_MODEL = "qwen3-next-80b-instruct-fp8"
MAX_WORKERS = 16
MAX_RETRIES = 3
REPO_ROOT = Path(__file__).resolve().parent.parent


# ── vLLM API ─────────────────────────────────────────────────────────────────


def call_vllm_judge(
    question: str, response_text: str, *, url: str, model: str
) -> tuple[int, str]:
    """Send a judge request to the vLLM server. Returns (score, justification)."""
    user_content = DEFAULT_JUDGE_USER_TEMPLATE_NO_HINT.format(
        question=question,
        response=response_text,
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DEFAULT_JUDGE_SYSTEM_PROMPT_NO_HINT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            text = msg.get("content")
            if text is None:
                raise ValueError(
                    f"Model returned null content "
                    f"(finish_reason={resp.json()['choices'][0].get('finish_reason')})"
                )
            score, justification, _ = parse_judge_output(text)
            return score, justification
        except Exception as exc:
            last_err = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"vLLM judge failed after {MAX_RETRIES} attempts: {last_err}")


# ── Data loading ─────────────────────────────────────────────────────────────


def load_vanilla_rows() -> list[dict]:
    path = REPO_ROOT / "data" / "latest" / "aggregate.jsonl"
    rows = []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            rows.append(row)
    return rows


def load_thirdparty_rows() -> list[dict]:
    pattern = str(
        REPO_ROOT
        / "runs"
        / "run_v2_*thirdparty*"
        / "grade_panels"
        / "*"
        / "aggregates"
        / "*"
        / "aggregate.jsonl"
    )
    rows = []
    for path in sorted(glob.glob(pattern)):
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                row["_source_file"] = path
                rows.append(row)
    return rows


# ── Checkpoint logic ─────────────────────────────────────────────────────────


def load_checkpoint(path: Path) -> dict[str, dict]:
    """Load checkpoint file. Returns {sample_id: {score, justification, error}}."""
    results: dict[str, dict] = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                entry = json.loads(line)
                results[entry["sample_id"]] = entry
    return results


def append_checkpoint(path: Path, entry: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Judge runner ─────────────────────────────────────────────────────────────


def make_row_key(row: dict) -> str:
    """Unique key for a row — use sample_id plus source file for thirdparty."""
    source = row.get("_source_file", "vanilla")
    return f"{source}::{row['sample_id']}"


def judge_row(row: dict, *, url: str, model: str) -> dict:
    """Run the vLLM judge on one row. Returns checkpoint entry."""
    key = make_row_key(row)
    # Use prompt_question if available (thirdparty wraps question in a framing),
    # otherwise use question directly.
    question = row.get("prompt_question") or row["question"]
    try:
        score, justification = call_vllm_judge(
            question, row["response_text"], url=url, model=model
        )
        return {
            "sample_id": key,
            "vllm_score": score,
            "vllm_justification": justification,
            "error": None,
        }
    except Exception as exc:
        return {
            "sample_id": key,
            "vllm_score": None,
            "vllm_justification": None,
            "error": str(exc),
        }


def run_judging(
    rows: list[dict], checkpoint_path: Path, label: str,
    workers: int = MAX_WORKERS, *, url: str, model: str,
) -> dict[str, dict]:
    """Run vLLM judge on all rows with checkpointing. Returns results dict."""
    existing = load_checkpoint(checkpoint_path)
    to_judge = []
    for row in rows:
        key = make_row_key(row)
        if key not in existing:
            to_judge.append(row)

    print(f"[{label}] {len(rows)} total rows, {len(existing)} already done, "
          f"{len(to_judge)} remaining")

    if not to_judge:
        return existing

    done = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(judge_row, row, url=url, model=model): row
            for row in to_judge
        }
        for future in as_completed(futures):
            result = future.result()
            existing[result["sample_id"]] = result
            append_checkpoint(checkpoint_path, result)
            done += 1
            if result["error"]:
                errors += 1
            if done % 100 == 0 or done == len(to_judge):
                print(f"  [{label}] {done}/{len(to_judge)} "
                      f"(errors: {errors})")

    return existing


# ── Analysis ─────────────────────────────────────────────────────────────────


def compute_agreement(
    rows: list[dict], results: dict[str, dict], label: str,
    vllm_model: str = DEFAULT_VLLM_MODEL,
) -> None:
    """Compute and print pairwise agreement and Krippendorff's alpha."""
    judge_names = ["judge_1", "judge_2", "judge_3", "vllm"]

    # Build score matrix: list of (j1, j2, j3, vllm) per row
    score_rows: list[list[int | None]] = []
    valid_count = 0
    error_count = 0

    for row in rows:
        key = make_row_key(row)
        entry = results.get(key)
        if not entry or entry.get("error"):
            error_count += 1
            continue

        scores: list[int | None] = []
        for jn in ["judge_1", "judge_2", "judge_3"]:
            s = row.get(f"{jn}_score")
            scores.append(s if isinstance(s, int) else None)
        scores.append(entry["vllm_score"])
        score_rows.append(scores)
        valid_count += 1

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  Valid rows: {valid_count}, Errors: {error_count}")

    # Get judge model names from first row for display
    model_names = []
    if rows:
        for jn in ["judge_1", "judge_2", "judge_3"]:
            model_names.append(rows[0].get(f"{jn}_model", jn))
    model_names.append(f"vllm/{vllm_model}")

    # Pairwise agreement
    print(f"\n  Pairwise exact agreement:")
    for i in range(4):
        for j in range(i + 1, 4):
            agree = 0
            total = 0
            for sr in score_rows:
                if sr[i] is not None and sr[j] is not None:
                    total += 1
                    if sr[i] == sr[j]:
                        agree += 1
            rate = agree / total if total > 0 else 0
            name_i = model_names[i] if i < len(model_names) else f"judge_{i+1}"
            name_j = model_names[j] if j < len(model_names) else f"judge_{j+1}"
            print(f"    {name_i} vs {name_j}: "
                  f"{rate:.1%} ({agree}/{total})")

    # Per-score conditional agreement: when judge X gives score S, what does vLLM give?
    print(f"\n  Per-score agreement (vLLM vs each judge):")
    for i in range(3):
        name_i = model_names[i] if i < len(model_names) else f"judge_{i+1}"
        print(f"\n    {name_i}:")
        # For each score the existing judge gave, show vLLM's distribution
        for s in [0, 1, 2]:
            vllm_given: dict[int, int] = defaultdict(int)
            for sr in score_rows:
                if sr[i] == s and sr[3] is not None:
                    vllm_given[sr[3]] += 1
            total = sum(vllm_given.values())
            if total == 0:
                continue
            agree = vllm_given.get(s, 0)
            parts = []
            for vs in sorted(vllm_given):
                pct = vllm_given[vs] / total
                parts.append(f"vllm={vs}: {vllm_given[vs]} ({pct:.0%})")
            print(f"      when {name_i}={s} (n={total}): "
                  f"agree={agree/total:.0%}  [{', '.join(parts)}]")

    # Score distribution for vLLM
    vllm_dist: dict[int, int] = defaultdict(int)
    for sr in score_rows:
        if sr[3] is not None:
            vllm_dist[sr[3]] += 1
    print(f"\n  vLLM score distribution:")
    for s in sorted(vllm_dist):
        print(f"    Score {s}: {vllm_dist[s]}")

    # Confusion matrix: vLLM vs consensus
    print(f"\n  vLLM vs consensus score (rows x cols = vllm x consensus):")
    all_scores = sorted({0, 1, 2, 3})
    # Header
    print(f"    {'':>8}", end="")
    for cs in all_scores:
        print(f"  c={cs:>2}", end="")
    print()
    for vs in all_scores:
        print(f"    v={vs:>2}  ", end="")
        for cs in all_scores:
            count = 0
            for row, sr in zip(rows, score_rows):
                if sr[3] == vs:
                    cons = row.get("consensus_score")
                    if cons == cs:
                        count += 1
            print(f"  {count:>4}", end="")
        print()

    # Krippendorff's alpha — all 4 judges
    units_4: list[list[int]] = []
    for sr in score_rows:
        unit = [s for s in sr if s is not None]
        if len(unit) >= 2:
            units_4.append(unit)
    alpha_4 = krippendorff_alpha_ordinal(units_4)
    print(f"\n  Krippendorff's alpha (ordinal, all 4 judges): {alpha_4}")

    # Krippendorff's alpha — original 3 judges only
    units_3: list[list[int]] = []
    for sr in score_rows:
        unit = [s for s in sr[:3] if s is not None]
        if len(unit) >= 2:
            units_3.append(unit)
    alpha_3 = krippendorff_alpha_ordinal(units_3)
    print(f"  Krippendorff's alpha (ordinal, original 3 judges): {alpha_3}")

    # Krippendorff's alpha — vLLM vs each existing judge
    for i, name in enumerate(model_names[:3]):
        units_pair: list[list[int]] = []
        for sr in score_rows:
            if sr[i] is not None and sr[3] is not None:
                units_pair.append([sr[i], sr[3]])
        alpha_pair = krippendorff_alpha_ordinal(units_pair)
        print(f"  Krippendorff's alpha (vllm vs {name}): {alpha_pair}")

    # Per-control/non-control breakdown
    for is_ctrl in [False, True]:
        ctrl_label = "control" if is_ctrl else "non-control"
        ctrl_rows = [
            (row, sr) for row, sr in zip(rows, score_rows)
            if row.get("is_control") == is_ctrl
        ]
        if not ctrl_rows:
            continue
        print(f"\n  [{ctrl_label}] ({len(ctrl_rows)} rows)")
        for i in range(4):
            for j in range(i + 1, 4):
                agree = 0
                total = 0
                for _, sr in ctrl_rows:
                    if sr[i] is not None and sr[j] is not None:
                        total += 1
                        if sr[i] == sr[j]:
                            agree += 1
                if total > 0:
                    rate = agree / total
                    name_i = model_names[i] if i < len(model_names) else f"judge_{i+1}"
                    name_j = model_names[j] if j < len(model_names) else f"judge_{j+1}"
                    print(f"    {name_i} vs {name_j}: "
                          f"{rate:.1%} ({agree}/{total})")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare vLLM judge against existing 3-judge panel"
    )
    parser.add_argument("--url", default=None,
                        help="vLLM base URL (e.g. http://host:port)")
    parser.add_argument("--model", default=None,
                        help="Model name (auto-detected from server if omitted)")
    parser.add_argument("--vanilla", action="store_true",
                        help="Run on vanilla baseline data")
    parser.add_argument("--thirdparty", action="store_true",
                        help="Run on third-party formulation data")
    parser.add_argument("--checkpoint-dir", type=Path, default=None,
                        help="Directory for checkpoint files (default: data/vllm_judge_<model>/)")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS,
                        help="Number of parallel workers")
    parser.add_argument("--analysis-only", action="store_true",
                        help="Skip judging, just run analysis on existing checkpoints")
    args = parser.parse_args()

    if not args.vanilla and not args.thirdparty:
        parser.error("Specify at least one of --vanilla or --thirdparty")

    # Resolve URL and model
    base_url = (args.url or DEFAULT_VLLM_URL.rsplit("/v1/", 1)[0]).rstrip("/")
    api_url = f"{base_url}/v1/chat/completions"

    if args.model:
        model = args.model
    else:
        # Auto-detect from /v1/models
        resp = requests.get(f"{base_url}/v1/models", timeout=10)
        resp.raise_for_status()
        model = resp.json()["data"][0]["id"]
        print(f"Auto-detected model: {model}")

    # Sanitize model name for directory
    model_slug = model.replace("/", "_").replace(" ", "_")
    checkpoint_dir = args.checkpoint_dir or (REPO_ROOT / "data" / f"vllm_judge_{model_slug}")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    workers = args.workers

    print(f"Model: {model}")
    print(f"URL: {api_url}")
    print(f"Checkpoints: {checkpoint_dir}")

    if args.vanilla:
        rows = load_vanilla_rows()
        ckpt = checkpoint_dir / "vanilla.jsonl"
        if args.analysis_only:
            results = load_checkpoint(ckpt)
        else:
            results = run_judging(
                rows, ckpt, "vanilla", workers=workers, url=api_url, model=model
            )
        compute_agreement(rows, results, "Vanilla Baseline", vllm_model=model)

    if args.thirdparty:
        rows = load_thirdparty_rows()
        ckpt = checkpoint_dir / "thirdparty.jsonl"
        if args.analysis_only:
            results = load_checkpoint(ckpt)
        else:
            results = run_judging(
                rows, ckpt, "thirdparty", workers=workers, url=api_url, model=model
            )
        compute_agreement(rows, results, "Third-Party Formulations", vllm_model=model)


if __name__ == "__main__":
    main()
