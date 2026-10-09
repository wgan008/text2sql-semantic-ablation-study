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

Gemini's **self-generated** schema descriptions (C1) *reduced* accuracy from 38% to 31% — worse than giving the model nothing but the raw schema. Swapping in BIRD's human-written descriptions (C2) instead lifted accuracy to 46%. Auto-documentation was actively misleading here, not merely unhelpful.

## Why C1 (auto-descriptions) underperforms

C1 is the only configuration that produced outright SQL execution errors (2 of 100 — `OperationalError`, vs. zero in every other config). Both are informative:

**1. Cross-table column confusion** (qid 14, `california_schools`):

```sql
SELECT T1.School, T2.NCESSchool, T1.`Enrollment (Ages 5-17)`
FROM frpm AS T1
INNER JOIN schools AS T2 ON T1.CDSCode = T2.CDSCode
...
```
→ `no such column: T1.School`. The actual schema has `frpm.\`School Name\`` and a *separate* `schools.School` column. The model picked the right column name but attributed it to the wrong table.

**2. Missing subquery alias** (qid 47, `california_schools`):

```sql
SELECT AVG(T1.num_schools_opened) FROM (
  SELECT STRFTIME('%m', OpenDate) AS month, COUNT(CDSCode) AS num_schools_opened
  FROM schools WHERE ...
  GROUP BY month
)
```
→ `no such column: T1.num_schools_opened`. The subquery is never aliased `AS T1`, so the outer reference doesn't resolve — a plain SQL-generation bug, independent of the description content.

The likely driver for (1): the auto-generated description file is a **flat list** — `table: summary` then `table.column: one-liner`, back-to-back for every table with no visual separation — unlike the human-written BIRD descriptions, which ship as **one CSV per table** and get concatenated with a `## <table>` markdown header per table (see `human_descriptions()` in `context.py`). Several tables in this schema have near-duplicate concepts ("school name" exists in both `frpm` and `schools` under different column names), and the unstructured auto-description format gives the model weaker table-boundary cues than the explicitly headered human descriptions — making this kind of cross-table mix-up more likely.

## Accuracy by difficulty

| Config | Simple (n=59) | Moderate (n=35) | Challenging (n=6) |
|---|---|---|---|
| C0 | 47% | 26% | 17% |
| C1 | 42% | 17% | 0% |
| C2 | 56% | 37% | 0% |
| C3 | 75% | 37% | 0% |
| C4 | 66% | 40% | 0% |

Context helps most on "simple" questions (47% → 75% from C0 to C3) and barely moves "moderate" questions. On "challenging" questions, **only C0 got anything right** — 1 of 6, by raw schema alone — and every context-enriched config (C1–C4) scored 0%. So added context didn't just fail to help on hard questions here; the single question that raw schema solved was *not* solved once any extra context was added, in every one of C1–C4. With n=6 this is too small to generalize, but it's a flag worth re-checking at higher difficulty-tier sample sizes rather than assuming "more context" is monotonically safe.

## Takeaways

- **Human-curated schema descriptions beat auto-generated ones, decisively.** C1 < C0 < C2 — the model's own guesses about column semantics were worse than no description at all, and produced the only outright SQL errors in the whole run (see above).
- **Business/domain evidence is the single highest-leverage addition.** C2 → C3 added +11pp overall, the largest jump of any step, concentrated in the "simple" tier (56% → 75%).
- **Few-shot verified queries (C4) did not help on top of C3** — accuracy fell slightly (57% → 53%). With only 3 retrieved examples selected by lexical token overlap, the retrieval may be too noisy to add signal once evidence is already present; worth re-testing with better retrieval or more examples.
- **More context is not uniformly safe.** The "challenging" tier result above (1/6 solved only without any added context) is a small-sample signal that extra context can occasionally crowd out a correct raw-schema answer — not just fail to help.

## Caveats

- n=100, 1 sample per question, 1 model (`gemini-2.5-flash`). 89 of the 100 questions come from a single database (`california_schools`), so these numbers mostly describe behavior on that schema — not a BIRD-wide result.
- No perturbed-database re-check was run on this pass, so coincidentally-correct SQL (right answer, wrong reasoning) isn't filtered out.
- `samples_per_question: 1` means no variance/confidence estimate per cell — repeat runs could move these numbers by a few points, especially on small slices like the 6-question "challenging" tier.
