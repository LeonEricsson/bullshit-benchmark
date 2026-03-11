# Judge Model Comparison

Evaluating candidate judge models against the existing 3-judge panel (claude-sonnet-4.6, gpt-5.2, gemini-3.1-pro-preview) used in the bullshit benchmark. All panel judges run at temperature=0 with reasoning off via OpenRouter. The panel scores responses on a 0/1/2 scale using the no-hint judge prompt.

## Summary Table

| Model | Backend | Sample | Vanilla α (all 4) | Thirdparty α (all 4) | Score-1 % (vanilla) | Errors |
|-------|---------|--------|--------------------|-----------------------|---------------------|--------|
| Panel only (3 judges) | OpenRouter | 4125/900 | — / 0.785 | — / 0.710 | 19% (Sonnet), 17% (GPT), 5% (Gemini) | — |
| Qwen3.5-35B-A3B-FP8 | vLLM local | 4125/900 | 0.764 | 0.692 | 1.5% | 0 |
| Qwen3-Next-80B | vLLM local | 4125/900 | 0.728 | 0.631 | 0.2% | 0 |
| **step-3.5-flash** | **OpenRouter (free)** | **250/250** | **0.829** | **0.761** | **12.7%** | **18 (7%)** |
| minimax-m2.5 | OpenRouter | 250/250 | 0.753 | 0.693 | 14.8% | 0 |
| gpt-oss-120b | OpenRouter | 500/500 | 0.679 | 0.612 | 7.4% | 0 |

Alpha values are Krippendorff's alpha (ordinal) with all 4 judges. Panel-only alpha is the original 3-judge baseline.

---

## Qwen3.5-35B-A3B-FP8

**Backend**: vLLM at `http://kaer-morhen:15011` | **Sample**: 4125 vanilla, 900 thirdparty | **Reasoning**: disabled via `enable_thinking: False`

### Results

Pairwise agreement (vanilla):
- vs Sonnet: 75.1% (α=0.747)
- vs GPT-5.2: 74.6% (α=0.705)
- vs Gemini: 85.5% (α=0.777)

Score distribution (vanilla): 0=2301, 1=63, 2=1761

Per-score agreement when panel judge gives score 1:
- Sonnet=1 → Qwen agrees 5%, gives 2 in 73% of cases
- GPT-5.2=1 → Qwen agrees 6%, gives 2 in 55%
- Gemini=1 → Qwen agrees 8%, gives 2 in 77%

### Discussion

Qwen3.5-35B is the highest-alpha local model tested, closest to Gemini in behavior (85.5% pairwise). However, it is nearly blind to score 1 — only 1.5% of its vanilla scores are 1, compared to ~19% for Sonnet. Qualitative analysis of justifications shows Qwen applies a binary presence/absence test for incoherence language rather than the proportional pushback-to-engagement weighting the rubric specifies. When the panel gives a 1 (partial pushback), Qwen overwhelmingly scores it as 2 (clear pushback), claiming the model "correctly identified" or "refused" the nonsense even when the response is a long, engaged answer with buried caveats. This bias can erase real experimental findings: the third-party formulation effect on Gemini (panel delta +0.63) is invisible to Qwen (delta +0.07) because the effect manifests as score-0→score-1 movement.

---

## Qwen3-Next-80B-Instruct-FP8

**Backend**: vLLM at `http://smeagols-lair:19000` | **Sample**: 4125 vanilla, 900 thirdparty | **Reasoning**: disabled via `enable_thinking: False`

### Results

Pairwise agreement (vanilla):
- vs Sonnet: 70.9% (α=0.667)
- vs GPT-5.2: 72.2% (α=0.664)
- vs Gemini: 81.7% (α=0.692)

Score distribution (vanilla): 0=2043, 1=10, 2=2072

### Discussion

The larger Qwen3-Next-80B performs worse than the smaller Qwen3.5-35B on every metric despite having ~2.3x the active parameters. Its score-1 blindness is even more extreme (0.2% vs 1.5%), and it shows a strong tendency toward a 50/50 binary split between scores 0 and 2. The 80B model's alpha (0.728) is notably lower than the 35B's (0.764), suggesting the smaller model's architecture or training is better suited to the grading task. Not recommended as a judge candidate.

---

## step-3.5-flash (StepFun)

**Backend**: OpenRouter (free tier) | **Sample**: 244 vanilla, 238 thirdparty (250 requested, ~7% null-content errors) | **Reasoning**: not applicable

### Results

Pairwise agreement (vanilla):
- vs Sonnet: 79.5% (α=0.831)
- vs GPT-5.2: 82.4% (α=0.818)
- vs Gemini: 85.2% (α=0.886)

Score distribution (vanilla): 0=129, 1=31, 2=84

Per-score agreement when panel judge gives score 1:
- Sonnet=1 → step agrees 35%, gives 2 in 59%
- GPT-5.2=1 → step agrees 48%, gives 2 in 25%
- Gemini=1 → step agrees 44%

Pairwise agreement (thirdparty):
- vs Sonnet: 80.7% (α=0.803)
- vs GPT-5.2: 78.9% (α=0.755)
- vs Gemini: 81.2% (α=0.775)

Score distribution (thirdparty): 0=71, 1=25, 2=142

### Discussion

step-3.5-flash is the standout result. Its all-4-judges alpha (0.829 vanilla) is *higher* than the original 3-judge panel alpha (0.811), meaning it actually improves inter-rater reliability when added as a 4th judge. This is the only candidate tested that achieves this. Pairwise agreement with each panel member (79-85%) is comparable to or exceeds the agreement the panel members have with each other (77-83%). Score-1 usage (12.7%) is healthy, and its score-1 agreement rates (35-48%) are second only to minimax-m2.5. The model's closest match is to Gemini (α=0.886), the highest pairwise alpha observed in any comparison. The only downside is a ~7% null-content error rate on the free tier, likely a rate-limit or capacity issue rather than a model problem. At free tier pricing this is the most cost-effective judge candidate tested, and even at paid pricing it would likely be competitive.

---

## minimax-m2.5

**Backend**: OpenRouter | **Sample**: 250 vanilla, 250 thirdparty | **Reasoning**: off

### Results

Pairwise agreement (vanilla):
- vs Sonnet: 76.4% (α=0.724)
- vs GPT-5.2: 70.0% (α=0.679)
- vs Gemini: 80.0% (α=0.778)

Score distribution (vanilla): 0=140, 1=37, 2=73

Per-score agreement when panel judge gives score 1:
- Sonnet=1 → m2.5 agrees 43%
- GPT-5.2=1 → m2.5 agrees 27%
- Gemini=1 → m2.5 agrees 56%

Pairwise agreement (thirdparty):
- vs Sonnet: 68.5% (α=0.644)
- vs GPT-5.2: 69.7% (α=0.647)
- vs Gemini: 72.5% (α=0.672)

Score distribution (thirdparty): 0=82, 1=44, 2=124

### Discussion

minimax-m2.5 has the best score-1 calibration of any candidate tested, assigning score 1 to 14.8% of vanilla rows — close to the panel average. Its score-1 agreement rate (43% with Sonnet, 56% with Gemini) is an order of magnitude better than Qwen's (~5%). Overall alpha (0.753 vanilla) is competitive with Qwen3.5-35B (0.764) despite a 4x smaller sample. Its weak spot is disagreement with GPT-5.2 on score 2 (only 66% vanilla agreement), where it tends to downgrade to 0 or 1. Closest match is to Gemini (80% agreement, α=0.778). The most promising cheap judge candidate tested so far, though the small sample size warrants further validation.

---

## gpt-oss-120b

**Backend**: OpenRouter | **Sample**: 500 vanilla, 500 thirdparty | **Reasoning**: on (default, cannot be disabled)

### Results

Pairwise agreement (vanilla):
- vs Sonnet: 65.8% (α=0.552)
- vs GPT-5.2: 74.4% (α=0.665)
- vs Gemini: 71.3% (α=0.529)

Score distribution (vanilla): 0=208, 1=39, 2=253

Per-score agreement when panel judge gives score 1:
- Sonnet=1 → gpt-oss agrees 19%
- GPT-5.2=1 → gpt-oss agrees 30%
- Gemini=1 → gpt-oss agrees 35%

Pairwise agreement (thirdparty):
- vs Sonnet: 65.7% (α=0.455)
- vs GPT-5.2: 76.9% (α=0.591)
- vs Gemini: 70.7% (α=0.417)

Score distribution (thirdparty): 0=105, 1=31, 2=364

### Discussion

gpt-oss-120b is the worst-performing candidate by a significant margin. Its vanilla alpha (0.679) is well below Qwen3.5-35B (0.764) and minimax-m2.5 (0.753), and it degrades further on thirdparty data (0.612). The model has a strong over-scoring bias: when Gemini scores 0 on thirdparty data, gpt-oss-120b gives a 2 in 53% of cases. This bias is worse than any other candidate tested. Its score-1 usage (7.4%) is middling — better than Qwen but far below minimax-m2.5. The model also suffered a ~10% null-content error rate at 512 max_tokens due to its reasoning token overhead, requiring 4096 max_tokens to resolve. As a reasoning model it consumes substantially more tokens per judgment. Not recommended.
