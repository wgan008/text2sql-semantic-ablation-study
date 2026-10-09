"""Strict result-set comparison for execution accuracy.

Rules:
- Multiset semantics: duplicate rows matter (a missing DISTINCT is an error).
- Row order matters only when the gold query has ORDER BY.
- NULL equals NULL for comparison purposes.
- Numbers are compared after rounding (1 == 1.0, 0.1 + 0.2 == 0.3).
- Column names are ignored, and columns may appear in a different order.
"""
from __future__ import annotations

import itertools
import re
from collections import Counter
from decimal import Decimal
from typing import Any, Sequence

_NULL = ("<NULL>",)
_ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)
MAX_PERMUTATIONS = 5040  # 7! ; beyond this, fall back to identity order only


def has_order_by(sql: str) -> bool:
    """Approximate: true if the outermost query ends with ORDER BY.

    Strips trailing LIMIT/semicolons and checks the last ORDER BY sits at depth 0.
    """
    s = sql.strip().rstrip(";")
    for m in reversed(list(_ORDER_BY.finditer(s))):
        tail = s[m.end():]
        if tail.count("(") == tail.count(")") and s[: m.start()].count("(") == s[: m.start()].count(")"):
            return True
    return False


def normalize_value(v: Any, precision: int = 6) -> Any:
    if v is None:
        return _NULL
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float, Decimal)):
        return round(float(v), precision)
    if isinstance(v, bytes):
        return v.hex()
    return str(v).strip()


def normalize_rows(rows: Sequence[Sequence[Any]], precision: int = 6) -> list[tuple]:
    return [tuple(normalize_value(v, precision) for v in row) for row in rows]


def _column_permutations(gold: list[tuple], pred: list[tuple]):
    """Yield column orders for pred that could match gold, pruned by column multisets."""
    n = len(gold[0])
    gold_cols = [Counter(r[i] for r in gold) for i in range(n)]
    pred_cols = [Counter(r[i] for r in pred) for i in range(n)]
    candidates = [[j for j in range(n) if pred_cols[j] == gold_cols[i]] for i in range(n)]
    if any(not c for c in candidates):
        return
    count = 0
    for perm in itertools.product(*candidates):
        if len(set(perm)) != n:
            continue
        yield perm
        count += 1
        if count >= MAX_PERMUTATIONS:
            return


def results_match(
    gold_rows: Sequence[Sequence[Any]],
    pred_rows: Sequence[Sequence[Any]],
    ordered: bool = False,
    precision: int = 6,
) -> bool:
    gold = normalize_rows(gold_rows, precision)
    pred = normalize_rows(pred_rows, precision)

    if len(gold) != len(pred):
        return False
    if not gold:
        return True
    if len(gold[0]) != len(pred[0]):
        return False

    for perm in _column_permutations(gold, pred):
        reordered = [tuple(row[j] for j in perm) for row in pred]
        if ordered:
            if reordered == gold:
                return True
        elif Counter(reordered) == Counter(gold):
            return True
    return False
