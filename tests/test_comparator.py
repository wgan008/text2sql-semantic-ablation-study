from text2sql_ablation.comparator import has_order_by, results_match


def test_row_order_ignored_without_order_by():
    assert results_match([(1, "a"), (2, "b")], [(2, "b"), (1, "a")])


def test_row_order_enforced_with_order_by():
    assert not results_match([(1,), (2,)], [(2,), (1,)], ordered=True)


def test_duplicates_matter():
    assert not results_match([(1,), (1,)], [(1,)])


def test_null_and_float_handling():
    assert results_match([(None, 0.3)], [(None, 0.1 + 0.2)])
    assert results_match([(1,)], [(1.0,)])


def test_column_permutation():
    assert results_match([(1, "x"), (2, "y")], [("x", 1), ("y", 2)])


def test_column_permutation_must_keep_rows_aligned():
    assert not results_match([(1, "x"), (2, "y")], [("y", 1), ("x", 2)])


def test_has_order_by_outer_only():
    assert has_order_by("SELECT a FROM t ORDER BY a DESC LIMIT 5")
    assert not has_order_by("SELECT * FROM (SELECT a FROM t ORDER BY a) x")
