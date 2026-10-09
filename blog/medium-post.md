# I let Gemini document its own database — then watched it write worse SQL because of it

*A small ablation study on how much "semantic context" actually helps Text-to-SQL, and where an LLM's own documentation backfires.*

Code, config, and full results: **[github.com/wgan008/text2sql-semantic-ablation-study](https://github.com/wgan008/text2sql-semantic-ablation-study)**

---

## TL;DR

- Giving a model **human-written** column descriptions beats giving it **nothing**, which beats giving it the model's **own auto-generated** descriptions. Auto-documentation was actively misleading, not just unhelpful.
- The single biggest accuracy jump came from adding **business/domain evidence** (a short glossary of domain-specific terms) — bigger than any schema-description change.
- Adding a handful of **retrieved few-shot examples** on top of everything else didn't help, and slightly hurt.
- None of this was free on hard questions — on genuinely difficult SQL, more context didn't rescue the model, and in one small-sample case it actively took away a correct answer.

## The setup

Text-to-SQL systems are usually evaluated as one monolithic pipeline — swap the model, retest, repeat. That makes it hard to tell *which part* of the prompt is actually doing the work. So I ran a small ablation instead: same 100 questions from the [BIRD](https://bird-bench.github.io/) dev benchmark, same model (`gemini-2.5-flash`), same temperature (0.0) — and layered in one additional piece of context at a time:

| Config | What the model sees |
|---|---|
| **C0** | Just the raw database schema (DDL) |
| **C1** | C0 + descriptions Gemini generated for its own schema |
| **C2** | C0 + the *human-written* column descriptions BIRD ships with |
| **C3** | C2 + a short snippet of business/domain evidence per question |
| **C4** | C3 + three retrieved "verified" example queries (few-shot) |

Each question was scored once per config with a strict execution-accuracy check — the generated SQL has to return the *same result set* as the gold query, not just look plausible.

## The headline result

| Config | Accuracy |
|---|---|
| C0 — raw schema | 38% |
| C1 — + auto-generated descriptions | **31%** |
| C2 — + human-written descriptions | 46% |
| C3 — + business evidence | **57%** |
| C4 — + few-shot examples | 53% |

Two things jump out immediately.

### 1. The model's own documentation made it worse

I expected C1 to land somewhere between C0 and C2 — some help, just less polished than a human's. Instead it came in *below* raw schema alone: 31% vs. 38%. Letting Gemini describe its own tables and columns, then handing that description back to Gemini as context, was worse than giving it nothing extra at all.

Digging into the failures, C1 was the *only* configuration that produced outright SQL execution errors — the model referenced a column on the wrong table, and in another case referenced a subquery alias that didn't exist. My working theory: the auto-generated description was one long, flat, unheadered list for every table and column in the database, while the human-written version is split cleanly per table with explicit headers. A few tables in this schema have near-duplicate concepts (a "school name" column that exists under different names in two different tables) — and the flatter format seems to have given the model weaker table-boundary cues, making it easier to grab the right column name but attach it to the wrong table.

Interestingly, this regression wasn't universal — it showed up clearly on one database but not on a smaller second one in the sample, suggesting it may be schema-shape-dependent rather than a guaranteed failure mode of self-documentation in general. Worth testing on more schemas before generalizing.

### 2. Business evidence > fancier schema descriptions

The jump from C2 to C3 — adding a short, question-specific snippet of business/domain knowledge — was the largest single gain in the whole study (+11 points), concentrated almost entirely in questions BIRD labels "simple." That's a more useful lever than I expected going in: a terse glossary note about what a column *means in context* did more for accuracy than a longer, more thorough description of what the column *is*.

### 3. Few-shot examples didn't pull their weight

Adding three retrieved example queries on top of everything else (C4) didn't help — accuracy dipped slightly from 57% to 53%. The retrieval here was simple lexical token overlap between the question and a training set, which may just not be a good enough retriever to add signal once the model already has business evidence to work with. I wouldn't read too much into this without testing a better retriever or more examples.

## Where context didn't help at all

Splitting results by BIRD's difficulty labels tells a less rosy story on the hard end:

| Config | Simple | Moderate | Challenging |
|---|---|---|---|
| C0 | 47% | 26% | 17% |
| C1 | 42% | 17% | 0% |
| C2 | 56% | 37% | 0% |
| C3 | 75% | 37% | 0% |
| C4 | 66% | 40% | 0% |

Every meaningful gain from adding context landed on "simple" questions. On the 6 questions labeled "challenging," only the bare raw-schema config (C0) got anything right — and that one question was *not* solved by any config that added context on top. It's a six-question sample, so take it as a flag rather than a law, but it's a useful reminder that "more context" isn't a monotonically safe bet — it can occasionally crowd out a correct answer instead of adding one.

## What this pipeline doesn't do (yet)

Worth being upfront about two things this setup deliberately left out, since they're common pieces of more mature Text-to-SQL systems:

- **No reranking.** Each question/config pair gets exactly one generated SQL candidate — no generate-N-and-pick-the-best step.
- **No schema linking or pruning.** Every prompt gets the *entire* database schema, with no stage that first narrows it down to the tables/columns actually relevant to the question. On the two small schemas tested here that's harmless; on a much larger production schema it would likely both bloat the prompt and give the model more irrelevant columns to get confused by.

Both are natural next steps and could change some of the above — particularly the C1 auto-description failure mode, which might not survive a schema-linking stage that narrows the model's view to only the tables it actually needs.

## Full write-up

The complete breakdown — including a per-database split, the exact failing SQL from the auto-description errors, and caveats about sample size — is in [`results/FINDINGS.md`](https://github.com/wgan008/text2sql-semantic-ablation-study/blob/main/results/FINDINGS.md) in the repo. The evaluation harness (prompt builder, comparator, run loop) is all there too if you want to point it at a different model or a bigger slice of BIRD.
