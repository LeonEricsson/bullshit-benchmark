"""Compute token-usage vs performance correlations and output analysis JSON."""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "latest"
RESPONSES_PATH = DATA_DIR / "responses.jsonl"
AGGREGATE_PATH = DATA_DIR / "aggregate.jsonl"
OUTPUT_PATH = DATA_DIR / "token_analysis.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def extract_tokens(usage: dict[str, Any] | None) -> dict[str, int]:
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    details = usage.get("completion_tokens_details") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
        "completion_tokens": usage.get("completion_tokens", 0) or 0,
        "reasoning_tokens": details.get("reasoning_tokens", 0) or 0,
        "total_tokens": usage.get("total_tokens", 0) or 0,
    }


def pearson(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n < 3:
        return (float("nan"), float("nan"))
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return (float("nan"), float("nan"))
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
    # t-test for significance
    t = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else float("inf")
    # approximate two-tailed p-value using t-distribution (large n approx)
    p = _t_to_p(t, n - 2)
    return (r, p)


def spearman(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n < 3:
        return (float("nan"), float("nan"))
    rx = _ranks(xs)
    ry = _ranks(ys)
    return pearson(rx, ry)


def _ranks(vals: list[float]) -> list[float]:
    indexed = sorted(enumerate(vals), key=lambda t: t[1])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _t_to_p(t: float, df: int) -> float:
    """Approximate two-tailed p-value from t-statistic using normal approx for df>=30,
    otherwise use a rough beta incomplete function approximation."""
    if math.isinf(t) or math.isnan(t):
        return 0.0 if math.isinf(t) else float("nan")
    # For reasonable df, use the regularized incomplete beta function approximation
    x = df / (df + t * t)
    if df >= 100:
        # normal approximation
        from math import erfc
        z = abs(t) * (1 - 1 / (4 * df)) / math.sqrt(1 + t * t / (2 * df))
        return erfc(z / math.sqrt(2))
    # Simple numerical approximation using continued fraction for I_x(a, b)
    a = df / 2.0
    b = 0.5
    p = _betainc(x, a, b)
    return min(1.0, max(0.0, p))


def _betainc(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a,b) via continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Use log-beta for numerical stability
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) / a
    # Lentz's continued fraction
    f = 1.0
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    f = d
    for m in range(1, 200):
        # even step
        numerator = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= d * c
        # odd step
        numerator = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        delta = d * c
        f *= delta
        if abs(delta - 1.0) < 1e-10:
            break
    return front * f


def compute_correlation(xs: list[float], ys: list[float], label: str) -> dict[str, Any]:
    pr, pp = pearson(xs, ys)
    sr, sp = spearman(xs, ys)
    return {
        "label": label,
        "n": len(xs),
        "pearson_r": _clean(pr),
        "pearson_p": _clean(pp),
        "spearman_r": _clean(sr),
        "spearman_p": _clean(sp),
    }


def _clean(v: float) -> float | None:
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, 6)


def main() -> None:
    responses = load_jsonl(RESPONSES_PATH)
    aggregates = load_jsonl(AGGREGATE_PATH)

    # Build lookup: sample_id -> aggregate row
    agg_by_id: dict[str, dict[str, Any]] = {}
    for row in aggregates:
        agg_by_id[row["sample_id"]] = row

    # Join and extract fields
    samples: list[dict[str, Any]] = []
    skipped = 0
    for resp in responses:
        sid = resp["sample_id"]
        agg = agg_by_id.get(sid)
        if not agg:
            skipped += 1
            continue
        tokens = extract_tokens(resp.get("response_usage"))
        score = agg.get("consensus_score")
        if score is None:
            skipped += 1
            continue
        samples.append({
            "sample_id": sid,
            "model_row": resp["model_row"],
            "model_org": resp["model_org"],
            "model_name": resp["model_name"],
            "model_reasoning_level": resp.get("model_reasoning_level", "default"),
            "is_control": resp.get("is_control", False),
            "question_id": resp["question_id"],
            "technique": resp.get("technique", ""),
            "consensus_score": score,
            **tokens,
        })

    print(f"Joined {len(samples)} samples ({skipped} skipped)")

    # Filter to nonsense questions only
    nonsense = [s for s in samples if not s["is_control"]]
    print(f"Nonsense-only: {len(nonsense)} samples")

    # Per-model aggregates
    by_model: dict[str, list[dict[str, Any]]] = {}
    for s in nonsense:
        by_model.setdefault(s["model_row"], []).append(s)

    per_model: list[dict[str, Any]] = []
    for model_row, rows in sorted(by_model.items()):
        first = rows[0]
        comp_tokens = [r["completion_tokens"] for r in rows]
        reas_tokens = [r["reasoning_tokens"] for r in rows]
        total_tokens = [r["total_tokens"] for r in rows]
        scores = [r["consensus_score"] for r in rows]

        green_count = sum(1 for s in scores if s == 2)
        red_count = sum(1 for s in scores if s == 0)
        n = len(rows)

        per_model.append({
            "model_row": model_row,
            "model_org": first["model_org"],
            "model_name": first["model_name"],
            "reasoning_level": first["model_reasoning_level"],
            "sample_count": n,
            "mean_completion_tokens": round(statistics.mean(comp_tokens), 1),
            "median_completion_tokens": round(statistics.median(comp_tokens), 1),
            "mean_reasoning_tokens": round(statistics.mean(reas_tokens), 1),
            "median_reasoning_tokens": round(statistics.median(reas_tokens), 1),
            "mean_total_tokens": round(statistics.mean(total_tokens), 1),
            "avg_score": round(statistics.mean(scores), 4),
            "green_rate": round(green_count / n, 4),
            "red_rate": round(red_count / n, 4),
        })

    # Sort by avg_score descending
    per_model.sort(key=lambda m: m["avg_score"], reverse=True)

    # Model-level correlations
    mean_comp = [m["mean_completion_tokens"] for m in per_model]
    median_comp = [m["median_completion_tokens"] for m in per_model]
    mean_reas = [m["mean_reasoning_tokens"] for m in per_model]
    avg_scores = [m["avg_score"] for m in per_model]
    green_rates = [m["green_rate"] for m in per_model]

    correlations: list[dict[str, Any]] = [
        compute_correlation(mean_comp, avg_scores, "mean_completion_tokens vs avg_score"),
        compute_correlation(median_comp, avg_scores, "median_completion_tokens vs avg_score"),
        compute_correlation(mean_comp, green_rates, "mean_completion_tokens vs green_rate"),
    ]

    # Reasoning-only correlations (models with non-zero reasoning tokens)
    reasoning_models = [m for m in per_model if m["mean_reasoning_tokens"] > 0]
    if len(reasoning_models) >= 3:
        rm_reas = [m["mean_reasoning_tokens"] for m in reasoning_models]
        rm_scores = [m["avg_score"] for m in reasoning_models]
        rm_green = [m["green_rate"] for m in reasoning_models]
        correlations.append(compute_correlation(rm_reas, rm_scores, "mean_reasoning_tokens vs avg_score (reasoning models only)"))
        correlations.append(compute_correlation(rm_reas, rm_green, "mean_reasoning_tokens vs green_rate (reasoning models only)"))

    # Per-question correlation: within each question, do verbose models score better?
    by_question: dict[str, list[dict[str, Any]]] = {}
    for s in nonsense:
        by_question.setdefault(s["question_id"], []).append(s)

    per_q_pearson_rs: list[float] = []
    for qid, qrows in by_question.items():
        if len(qrows) < 5:
            continue
        qcomp = [float(r["completion_tokens"]) for r in qrows]
        qscores = [float(r["consensus_score"]) for r in qrows]
        r, _ = pearson(qcomp, qscores)
        if r is not None and not math.isnan(r):
            per_q_pearson_rs.append(r)

    per_question_summary = None
    if per_q_pearson_rs:
        per_question_summary = {
            "n_questions": len(per_q_pearson_rs),
            "mean_pearson_r": round(statistics.mean(per_q_pearson_rs), 4),
            "median_pearson_r": round(statistics.median(per_q_pearson_rs), 4),
            "min_pearson_r": round(min(per_q_pearson_rs), 4),
            "max_pearson_r": round(max(per_q_pearson_rs), 4),
        }

    # Per-sample data for scatter plots (nonsense only)
    per_sample = [
        {
            "model_row": s["model_row"],
            "model_org": s["model_org"],
            "question_id": s["question_id"],
            "completion_tokens": s["completion_tokens"],
            "reasoning_tokens": s["reasoning_tokens"],
            "consensus_score": s["consensus_score"],
        }
        for s in nonsense
    ]

    output = {
        "generated": "token_analysis.py",
        "total_samples": len(nonsense),
        "total_models": len(per_model),
        "per_model": per_model,
        "correlations": correlations,
        "per_question_correlation": per_question_summary,
        "per_sample": per_sample,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {OUTPUT_PATH} ({len(per_model)} models, {len(per_sample)} samples)")
    for c in correlations:
        print(f"  {c['label']}: r={c['pearson_r']}, p={c['pearson_p']} (Pearson) | rho={c['spearman_r']}, p={c['spearman_p']} (Spearman)")
    if per_question_summary:
        print(f"  Per-question mean Pearson r: {per_question_summary['mean_pearson_r']} (over {per_question_summary['n_questions']} questions)")


if __name__ == "__main__":
    main()
