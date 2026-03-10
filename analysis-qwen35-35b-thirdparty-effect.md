# Third-Party Formulation Effect: Panel vs Qwen Judge Comparison

**Date:** 2026-03-10
**Question:** Does the choice of judge change conclusions about whether third-party framing improves model pushback?

## Setup

Five models appear in both the vanilla baseline and third-party formulation runs. We compare the third-party effect as measured by the 3-judge panel (claude-sonnet-4.6, gpt-5.2, gemini-3.1-pro-preview consensus) against Qwen3.5-35B-A3B-FP8 as a standalone judge.

## Results

### Mean score delta (thirdparty minus vanilla)

| Model | Panel | Qwen |
|---|---|---|
| claude-sonnet-4.5 | +0.37 | +0.36 |
| gpt-5.2 | +0.48 | +0.47 |
| gpt-5.2-chat | +0.45 | +0.47 |
| gpt-5.2-codex | +0.48 | +0.56 |
| gemini-3.1-pro | **+0.63** | **+0.07** |
| All overlapping | +0.45 | +0.34 |

### Binarized pushback rate (score > 0)

| Model | Panel vanilla | Panel thirdparty | Qwen vanilla | Qwen thirdparty |
|---|---|---|---|---|
| claude-sonnet-4.5 | 86% | 95% | 75% | 92% |
| gemini-3.1-pro | 38% | 77% | 32% | 36% |
| gpt-5.2 | 65% | 84% | 56% | 80% |
| gpt-5.2-chat | 45% | 72% | 35% | 57% |
| gpt-5.2-codex | 64% | 78% | 44% | 72% |

### Gemini detail: panel judge score distributions

|  | Vanilla S0 | Vanilla S1 | Vanilla S2 | Thirdparty S0 | Thirdparty S1 | Thirdparty S2 |
|---|---|---|---|---|---|---|
| Sonnet | 69% | 13% | 18% | 28% | 32% | 40% |
| GPT | 62% | 11% | 27% | 25% | 26% | 49% |
| Gemini judge | 73% | 1% | 26% | 36% | 8% | 56% |
| Qwen | 68% | 2% | 30% | 64% | 2% | 34% |

## Discussion

For four of five models, Qwen and the panel agree on the direction and approximate magnitude of the third-party effect. The exception is Gemini, where the panel reports the largest effect (+0.63 mean, pushback rate 38%→77%) and Qwen reports almost none (+0.07 mean, pushback rate 32%→36%).

The discrepancy traces to how the third-party framing changes Gemini's responses. Rather than producing outright refusals, Gemini shifts from fully accepting the nonsensical premise to raising partial concerns while still answering — exactly the behavior the score-1 category is designed to capture. The panel's individual judges all see a large increase in score-1 assignments on Gemini thirdparty rows (Sonnet: 13%→32%, GPT: 11%→26%). Qwen, which assigns score 1 to only 1.5% of rows overall, cannot detect this shift.

This is not a minor calibration issue. The panel's single strongest finding — that third-party framing nearly doubles Gemini's pushback rate — disappears entirely under Qwen. The bias is systematic: Qwen treats the presence or absence of explicit incoherence language as the judging criterion, rather than weighing the proportion of pushback to engagement as the rubric specifies. Any model whose pushback style is subtle (hedging, redirecting, raising concerns without refusing) will be systematically misevaluated.

Qwen performs well as a judge on clear-cut cases (86-95% agreement on unambiguous score-0 and score-2 rows) and could serve as a cheap tiebreaker or sanity check. It is not suitable as a standalone judge or panel replacement for analyses where the score-1 category carries meaningful signal — particularly comparisons across prompting strategies or model personality differences, where the effect concentrates in partial pushback.
