# vLLM Judge Comparison: Qwen3-Next-80B vs 3-Judge Panel

**Date:** 2026-03-10
**Model:** qwen3-next-80b-instruct-fp8 (vLLM, http://smeagols-lair:19000)
**Panel:** claude-sonnet-4.6, gpt-5.2, gemini-3.1-pro-preview
**Prompt mode:** no-hint (judge receives no indication the question may be nonsensical)
**Data:** 4125 vanilla baseline rows, 900 third-party formulation rows

## Score distributions

| Model | Score 0 | Score 1 | Score 2 |
|---|---|---|---|
| claude-sonnet-4.6 | 54.8% | 19.1% | 26.0% |
| gpt-5.2 | 45.7% | 16.6% | 37.7% |
| gemini-3.1-pro-preview | 62.5% | 4.7% | 32.7% |
| qwen3-next-80b (vLLM) | 49.5% | 0.2% | 50.2% |

## Results

On the vanilla baseline, Qwen achieves 70.9-81.7% pairwise exact agreement with the existing judges, compared to 78.5-83.8% among the panel members themselves. Its best match is with Gemini (81.7% exact, Krippendorff's alpha 0.69). On third-party formulations, agreement drops across the board: Qwen ranges 66.3-76.6% vs the panel's 74.3-78.4%, again tracking closest to Gemini. Krippendorff's alpha (ordinal) for all four judges is 0.728 on vanilla and 0.631 on third-party, compared to 0.785 and 0.710 for the original three-judge panel alone.

Per-score conditional analysis reveals where the disagreement concentrates. On score 0 (model accepted the nonsense) and score 2 (model clearly called it out), Qwen agrees with the panel at high rates: 79-88% on 0s and 85-99% on 2s across judges. On score 1 (partial pushback), agreement is essentially zero. When any existing judge assigns a 1, Qwen scores it as 2 roughly 76-93% of the time. It used score 1 only 10 times out of 4125 vanilla rows.

## Discussion

Qwen treats the judging task as binary: did the model push back on the nonsensical premise, or didn't it? The existing panel judges, particularly Sonnet and GPT, use score 1 as a meaningful middle category (17-19% of scores) for responses that raise concerns but still substantially answer the question. Gemini already leans toward this binary pattern with only 4.7% score-1s, and Qwen takes it to the extreme at 0.2%.

This isn't a quality problem per se — Qwen reliably distinguishes between responses that accept nonsense and responses that challenge it. The question is whether the score-1 category ("user might pause but probably wouldn't reconsider") captures a real distinction worth measuring. If so, Qwen can't serve as a drop-in replacement for the current panel without losing that granularity. If score 1 is mostly noise between annotators anyway, then Qwen's binary signal may be just as informative, and its high agreement on the endpoints supports that.

For practical use as a cost-effective replacement judge, Qwen could work well in a binarized evaluation (0 vs 2) or as a tiebreaker among the existing panel, but not as a sole judge if the three-level rubric is important.
