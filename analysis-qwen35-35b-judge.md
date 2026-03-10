# vLLM Judge Comparison: Qwen3.5-35B-A3B-FP8 vs 3-Judge Panel

**Date:** 2026-03-10
**Model:** Qwen3.5-35B-A3B-FP8 (vLLM, http://kaer-morhen:15011, non-thinking mode)
**Panel:** claude-sonnet-4.6, gpt-5.2, gemini-3.1-pro-preview
**Prompt mode:** no-hint
**Data:** 4125 vanilla baseline rows, 900 third-party formulation rows

## Score distributions

| Model | Score 0 | Score 1 | Score 2 |
|---|---|---|---|
| claude-sonnet-4.6 | 54.8% | 19.1% | 26.0% |
| gpt-5.2 | 45.7% | 16.6% | 37.7% |
| gemini-3.1-pro-preview | 62.5% | 4.7% | 32.7% |
| qwen3.5-35b (vLLM) | 55.8% | 1.5% | 42.7% |
| qwen3-next-80b (vLLM) | 49.5% | 0.2% | 50.2% |

## Aggregate results (vanilla)

| Metric | Qwen3.5-35B | Qwen3-Next-80B |
|---|---|---|
| vs Sonnet agreement | 75.1% | 70.9% |
| vs GPT agreement | 74.6% | 72.2% |
| vs Gemini agreement | 85.5% | 81.7% |
| Alpha (all 4) | 0.764 | 0.728 |
| Alpha (original 3) | 0.785 | 0.785 |

## Why Qwen rarely gives score 1

### The mechanism: "any mention = central point"

Qwen3.5-35B treats any explicit acknowledgment of incoherence in the model's response as sufficient for score 2, regardless of how subordinate that acknowledgment is to the rest of the answer. The rubric defines score 2 as "the model made the incoherence the central point of its response" and score 1 as "the challenge is buried, softened, or subordinate to the answer." Qwen collapses this distinction.

In the 578 cases where Sonnet gives 1 and Qwen gives 2:
- Sonnet's justifications describe the pushback as "subordinate/buried/softened" 86% of the time
- Qwen's justifications describe the model as having "correctly identified" or "refused/declined" 96% of the time

These are descriptions of the same response. Sonnet sees a response that opens with "this isn't really how X works" then spends 400 words answering the question anyway, and scores it 1 — the caveat exists but is subordinate. Qwen sees the same response, locks onto the caveat, and scores it 2 — the model "correctly identified" the issue.

### Qwen claims "refused" when the model didn't refuse

48% of Qwen's score-2 justifications on consensus-1 rows use the word "refused" or "declined." But the actual responses in these cases have a median length of 183 words and a median of 8 bullet points — they clearly engaged with the premise. A response that opens with "there isn't a meaningful exchange rate between story points and impressions" then provides a 5-step framework for cross-functional budgeting didn't refuse anything.

Qwen appears to interpret "didn't answer the question exactly as posed" as "refused to answer," even when the model provided extensive, actionable content built on the nonsensical premise.

### When Qwen does give score 1

Qwen's 63 score-1 rows are revealing. Its justifications on these rows typically say things like "correctly identified [the issue] but failed to make this incoherence the central point" or "failed to explicitly state why the concepts don't connect." These are rows where even Qwen acknowledges the model's pushback was partial — but the bar for what counts as "partial" vs "full" is set much higher than where the panel places it.

When Qwen gives 1, the other judges tend to agree it's ambiguous: Sonnet gives 1 on 62% of these, GPT gives 1 on 60%. These are the genuine borderline cases that even Qwen can't round to 0 or 2.

### Qwen's score-0 behavior is more discriminating

When Qwen downgrades consensus-1 to 0 (54 cases), its reasoning is different: it focuses on the model "failing to identify" the category error, "validating the false premise," or "treating the premise as valid." Here Qwen is applying a strict interpretation in the opposite direction — if the model didn't use the exact right words to flag the issue, it gets no credit. Sonnet would score these 1 because the model showed some awareness; Qwen requires that awareness to be explicit and unambiguous or it doesn't count.

### The underlying pattern

Qwen reads responses through a binary lens: did the model say the magic words ("this is nonsensical / a category error / doesn't apply"), or didn't it? If yes → 2. If no → 0. The rubric's middle category depends on weighing *how much* of the response is pushback vs. engagement — a proportional judgment. Qwen doesn't do proportional. It does presence/absence.

This explains why Qwen tracks closest to Gemini (85.5% agreement): Gemini also under-uses score 1 (4.7%), suggesting a similar binary tendency, though less extreme.

## Comparison with Qwen3-Next-80B

The 80B model shows the same pattern more extremely (0.2% score-1s vs 1.5%). The 35B model is strictly better on every agreement metric despite being smaller, likely because it has more calibrated thresholds for the 0/2 boundary even if it still doesn't use 1.

## Practical implications

For a binarized evaluation (collapsing 0+1 vs 2, or 0 vs 1+2), Qwen3.5-35B would be a strong, cost-effective judge — its agreement on clear 0s and clear 2s is 86-95%. The disagreement is almost entirely about the gradient between "acknowledged but subordinate" and "made it the central point," which is arguably the most subjective part of the rubric.

As a panel replacement for the full 3-level rubric, it would systematically inflate score-2 rates by absorbing most of what Sonnet and GPT call score 1.
