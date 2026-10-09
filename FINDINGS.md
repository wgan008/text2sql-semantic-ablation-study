# Text-to-SQL Semantic Context Ablation — Findings

**Run:** `results/20261009-104158/results.jsonl` · BIRD dev subset, **100 questions** · model `gemini-2.5-flash` · temperature 0.0 · 1 sample/question

## Question

How much does each layer of semantic context contribute to Text-to-SQL execution accuracy, and is an LLM's own auto-generated schema documentation a substitute for human-curated context?

## Configurations

| Config | Context given to the model |
|---|---|
| C0 | Raw schema (DDL) only |
| C1 | C0 + Gemini **auto-generated** table/column descriptions |
| C2 | C0 + **human-written** column descriptions (BIRD's own description files) |
| C3 | C2 + business evidence / glossary (BIRD `evidence` field) |
| C4 | C3 + 3 retrieved verified example queries (few-shot) |

## Overall accuracy

| Config | Accuracy |
|---|---|
| C0 | `███████████████` 38% |
| C1 | `████████████` 31% |
| C2 | `██████████████████` 46% |
| C3 | `██████████████████████` 57% |
| C4 | `█████████████████████` 53% |

- Gemini's **self-generated** schema descriptions (C1) *reduced* accuracy from 38% to 31% — worse than giving the model nothing but the raw schema.
- Swapping in BIRD's human-written descriptions (C2) instead lifted accuracy to 46%.
- Auto-documentation was actively misleading here, not merely unhelpful.

## Accuracy by business domain/database

| Database | n | C0 | C1 | C2 | C3 | C4 |
|---|---|---|---|---|---|---|
| `california_schools` (education) | 89 | 42% | 30% | 46% | 57% | 53% |
| `financial` (banking) | 11 | 9% | 36% | 45% | 55% | 55% |

- The C1 regression (auto-descriptions hurting accuracy) only shows up on `california_schools`; on `financial`, C1 is *better* than C0 (9% → 36%).
- C2 → C3 (adding business evidence) helps on both domains.
- C4 (few-shot examples) is flat-to-slightly-down on both domains vs. C3.
- 89 of 100 questions are from `california_schools`, so the headline numbers above are mostly a `california_schools` result — `financial` (n=11) is too small to trust on its own, but it doesn't contradict the overall pattern.

## Why C1 (auto-descriptions) underperforms

- C1 is the only config with outright SQL execution errors (2 of 100 `OperationalError`, vs. 0 elsewhere).
- Both errors are column-resolution failures: one query referenced a column on the wrong table alias (`T1.School` when `School` belongs to the other joined table); the other referenced a subquery alias that was never defined.
- Likely cause: the auto-generated description is one flat, unheadered list for the whole schema, while the human-written descriptions are split per table with clear headers — weaker table-boundary cues make this kind of cross-table mix-up more likely.

## Accuracy by difficulty

| Config | Simple (n=59) | Moderate (n=35) | Challenging (n=6) |
|---|---|---|---|
| C0 | 47% | 26% | 17% |
| C1 | 42% | 17% | 0% |
| C2 | 56% | 37% | 0% |
| C3 | 75% | 37% | 0% |
| C4 | 66% | 40% | 0% |

- Context helps most on "simple" questions (47% → 75% from C0 to C3) and barely moves "moderate" questions.
- On "challenging" questions, only C0 got anything right (1 of 6, raw schema only); every context-enriched config (C1–C4) scored 0%.
- That one challenging question solved by C0 was *not* solved by any of C1–C4 — a small-sample (n=6) signal, but worth re-checking at scale rather than assuming more context is always safe.

## Takeaways

- **Human-curated schema descriptions beat auto-generated ones, decisively.** C1 < C0 < C2 — the model's own guesses about column semantics were worse than no description at all, and produced the only outright SQL errors in the whole run.
- **Business/domain evidence is the single highest-leverage addition.** C2 → C3 added +11pp overall, the largest jump of any step, concentrated in the "simple" tier (56% → 75%).
- **Few-shot verified queries (C4) did not help on top of C3** — accuracy fell slightly (57% → 53%). With only 3 retrieved examples selected by lexical token overlap, the retrieval may be too noisy to add signal once evidence is already present; worth re-testing with better retrieval or more examples.
- **The auto-description regression isn't universal** — it shows up on `california_schools` but not `financial`, so it may be schema-shape-dependent (e.g. near-duplicate column concepts across tables) rather than a blanket effect.
- **More context is not uniformly safe.** The challenging-tier result above is a small-sample signal that extra context can occasionally crowd out a correct raw-schema answer — not just fail to help.

## Caveats

- n=100, 1 sample per question, 1 model (`gemini-2.5-flash`). 89 of the 100 questions come from a single database (`california_schools`), so these numbers mostly describe behavior on that schema — not a BIRD-wide result.
- No perturbed-database re-check was run on this pass, so coincidentally-correct SQL (right answer, wrong reasoning) isn't filtered out.
- `samples_per_question: 1` means no variance/confidence estimate per cell — repeat runs could move these numbers by a few points, especially on small slices like the 6-question "challenging" tier.
