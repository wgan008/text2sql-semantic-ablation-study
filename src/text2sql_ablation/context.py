"""Builds the prompt context for each ablation configuration.

C0 raw schema | C1 + auto descriptions | C2 + human descriptions
C3 C2 + evidence | C4 C3 + verified queries
"""
from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from .llm import generate_text

_AUTO_DESC_DIR = Path("data/auto_desc")
_TRAIN_PATH = Path("data/bird_train/train.jsonl")


def schema_ddl(db_path: Path) -> str:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
        ).fetchall()
    return "\n\n".join(r[0] for r in rows)


def sample_rows(db_path: Path, limit: int = 3) -> str:
    with sqlite3.connect(db_path) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        parts = []
        for t in tables:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
            rows = conn.execute(f'SELECT * FROM "{t}" LIMIT {limit}').fetchall()
            lines = [", ".join(cols)]
            lines += [", ".join(str(v)[:60] for v in r) for r in rows]
            parts.append(f"{t}:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def auto_descriptions(db_path: Path, client, model: str) -> str:
    cache_file = _AUTO_DESC_DIR / f"{db_path.stem}.md"
    if cache_file.exists():
        return cache_file.read_text()

    prompt = (
        "You are documenting a SQLite database schema. For each table and column "
        "below, write a one-line plain-English description of what it most likely "
        "represents, based on its name, type, and sample values. Be concise, no "
        "preamble.\n\n"
        f"### Schema\n{schema_ddl(db_path)}\n\n"
        f"### Sample rows\n{sample_rows(db_path)}"
    )
    text = generate_text(client, model, prompt)
    _AUTO_DESC_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(text)
    return text


def human_descriptions(db_dir: Path) -> str:
    # BIRD ships per-table CSVs in <db_dir>/database_description/
    desc_dir = db_dir / "database_description"
    if not desc_dir.exists():
        return ""
    parts = []
    for f in sorted(desc_dir.glob("*.csv")):
        parts.append(f"## {f.stem}\n{f.read_text(errors='ignore')}")
    return "\n\n".join(parts)


@lru_cache(maxsize=1)
def _load_train_examples() -> tuple[dict, ...]:
    if not _TRAIN_PATH.exists():
        return ()
    with _TRAIN_PATH.open() as f:
        return tuple(json.loads(line) for line in f if line.strip())


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def verified_queries(question: dict, k: int = 3) -> str:
    train = _load_train_examples()
    if not train:
        return ""

    q_tokens = _tokenize(question["question"])
    scored = []
    for ex in train:
        t_tokens = _tokenize(ex["question"])
        if not q_tokens or not t_tokens:
            continue
        overlap = len(q_tokens & t_tokens) / len(q_tokens | t_tokens)
        scored.append((overlap, ex))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    examples = []
    for _, ex in scored[:k]:
        block = f"Q: {ex['question']}\n"
        if ex.get("evidence"):
            block += f"Evidence: {ex['evidence']}\n"
        block += f"SQL:\n```sql\n{ex['SQL']}\n```"
        examples.append(block)
    return "\n\n".join(examples)


def build_prompt(config: str, question: dict, db_dir: Path, client=None, model: str | None = None) -> str:
    db_path = db_dir / f"{question['db_id']}.sqlite"
    sections = [f"### Database schema\n{schema_ddl(db_path)}"]

    if config == "C1":
        sections.append(f"### Column descriptions\n{auto_descriptions(db_path, client, model)}")
    if config in ("C2", "C3", "C4"):
        sections.append(f"### Column descriptions\n{human_descriptions(db_dir)}")
    if config in ("C3", "C4") and question.get("evidence"):
        sections.append(f"### Business knowledge\n{question['evidence']}")
    if config == "C4":
        sections.append(f"### Verified example queries\n{verified_queries(question)}")

    sections.append(
        f"### Question\n{question['question']}\n\n"
        "Write one SQLite query that answers the question. Return only SQL in a ```sql block."
    )
    return "\n\n".join(sections)
