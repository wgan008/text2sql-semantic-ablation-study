# text2sql-semantic-ablation-study

How much does each layer of semantic context contribute to Text-to-SQL accuracy, and is Gemini's auto-generated context good enough compared with human-curated context?

## Experiment design

Each question in a BIRD subset is answered under five context configurations:

| ID | Context given to the model |
|----|----------------------------|
| C0 | Raw schema only (DDL) |
| C1 | + Gemini auto-generated table/column descriptions |
| C2 | + Human-written column descriptions (BIRD description files) instead of C1 |
| C3 | C2 + business knowledge / glossary (BIRD `evidence`) |
| C4 | C3 + verified queries (retrieved few-shot examples) |

Scoring uses execution accuracy with a strict result-set comparator (multiset semantics, `ORDER BY`-aware, NULL and float handling, column-permutation tolerant). A subset is also re-checked on perturbed databases to catch coincidentally correct SQL.

See [FINDINGS.md](FINDINGS.md) for results from a 100-question run.

## Repository layout

```
config/experiment.yaml      experiment settings (model, configs, sample size)
scripts/setup_gcp.sh        creates and wires up the GCP project
src/text2sql_ablation/
  comparator.py             result-set comparison (Day 1 core)
  llm.py                    Gemini client (API key or Vertex AI)
  run.py                    main evaluation loop
tests/                      unit tests
data/                       BIRD subset (git-ignored)
results/                    run outputs (git-ignored)
```

## Quickstart

```bash
# 1. Python environment
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. GCP project (edit the variables at the top of the script first)
bash scripts/setup_gcp.sh

# 3. Environment variables
cp .env.example .env   # then fill in values

# 4. Data: download the BIRD dev set from the official BIRD benchmark site
#    and unzip it into data/bird_dev/

# 5. Tests and a first run
pytest
python -m text2sql_ablation.run --config config/experiment.yaml
```

## Cost guardrails

- Local runs use DuckDB/SQLite (free) and the Gemini API free tier where possible.
- BigQuery queries are capped per query via `BQ_MAX_BYTES_BILLED`; set a daily query quota and a billing budget on the project as well.
