"""mlx/cv.py - the cross-validation splitters of the Machine Learning tab (López de Prado, Advances in Financial ML ch. 7 and 12).

Every row of simdata/mlx_dataset.npz is a bar i with a label decided at bar touch_k (i + 1 .. i + 24). Two rows whose windows overlap share
the future, so a plain K-fold leaks: a training bar whose label was still being decided inside the test window has seen the test period.
  PurgedKFold          - n_splits contiguous, time-ordered test folds; the training set drops every row whose label window [k15, touch_k]
                         overlaps the test fold's bars [first_k, last_k] (purging) and every row that starts within `embargo` bars after the
                         fold (embargo: the test rows' own labels reach up to 24 bars past last_k, and serial correlation reaches further).
  CombinatorialPurgedCV - the dataset cut into n_groups blocks; every choice of n_test_groups blocks is a split (C(6, 2) = 15), purged and
                         embargoed around each test block; the splits' test predictions are stitched into C(5, 1) = 5 full backtest paths.
Both return plain lists of (train_idx, test_idx) index arrays, so sklearn's StackingClassifier(cv=...) and cross_val_predict take them as is.
Rows must be sorted by k15 (data.py writes them so); the splitters check it."""
from itertools import combinations

import numpy as np


def _check(k15, touch_k):
    k15 = np.asarray(k15, dtype=np.int64)
    touch_k = np.asarray(touch_k, dtype=np.int64)
    if k15.ndim != 1 or k15.shape != touch_k.shape:
        raise ValueError("k15 and touch_k must be one-dimensional and the same length")
    if len(k15) and np.any(np.diff(k15) < 0):
        raise ValueError("rows must be sorted by k15")
    if np.any(touch_k < k15):
        raise ValueError("touch_k must be >= k15 (the label is decided at or after the bar)")
    return k15, touch_k


def purge_mask(k15, touch_k, first_k, last_k, embargo):
    """True for the rows a model may train on when bars first_k..last_k are the test window"""
    overlap = (k15 <= last_k) & (touch_k >= first_k)                      # the label window [k15, touch_k] touches the test bars
    after = (k15 > last_k) & (k15 <= last_k + embargo)                     # the embargo after the window
    return ~(overlap | after)


class PurgedKFold:
    """time-ordered contiguous test folds with purging and an embargo; split() -> [(train_idx, test_idx), ...]"""

    def __init__(self, n_splits=5, embargo=24):
        if n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        self.n_splits = int(n_splits)
        self.embargo = int(embargo)

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

    def split(self, k15, touch_k):
        k15, touch_k = _check(k15, touch_k)
        n = len(k15)
        out = []
        for test in np.array_split(np.arange(n), self.n_splits):
            if not len(test):
                continue
            keep = purge_mask(k15, touch_k, k15[test[0]], k15[test[-1]], self.embargo)
            keep[test] = False
            out.append((np.nonzero(keep)[0], test))
        return out

    def describe(self, k15, touch_k):
        """per fold: the bars of the test window and how many rows the purge and the embargo removed"""
        k15, touch_k = _check(k15, touch_k)
        rows = []
        for i, (tr, te) in enumerate(self.split(k15, touch_k)):
            rows.append({"fold": i + 1, "test_first_k": int(k15[te[0]]), "test_last_k": int(k15[te[-1]]), "n_test": int(len(te)),
                         "n_train": int(len(tr)), "n_purged": int(len(k15) - len(te) - len(tr))})
        return rows


class CombinatorialPurgedCV:
    """n_groups contiguous blocks; every n_test_groups-subset is a test set -> C(n_groups, n_test_groups) splits, each purged + embargoed
    around EVERY test block. paths(): which (split, block) test predictions form each of the C(n_groups-1, n_test_groups-1) backtest paths."""

    def __init__(self, n_groups=6, n_test_groups=2, embargo=24):
        if n_test_groups < 1 or n_test_groups >= n_groups:
            raise ValueError("need 1 <= n_test_groups < n_groups")
        self.n_groups = int(n_groups)
        self.n_test_groups = int(n_test_groups)
        self.embargo = int(embargo)

    def groups(self, n):
        return [g for g in np.array_split(np.arange(n), self.n_groups) if len(g)]

    def combos(self):
        return list(combinations(range(self.n_groups), self.n_test_groups))

    def split(self, k15, touch_k):
        k15, touch_k = _check(k15, touch_k)
        blocks = self.groups(len(k15))
        out = []
        for combo in self.combos():
            keep = np.ones(len(k15), dtype=bool)
            for g in combo:
                b = blocks[g]
                keep &= purge_mask(k15, touch_k, k15[b[0]], k15[b[-1]], self.embargo)
                keep[b] = False
            out.append((np.nonzero(keep)[0], np.concatenate([blocks[g] for g in combo])))
        return out

    def n_paths(self):
        from math import comb
        return comb(self.n_groups - 1, self.n_test_groups - 1)

    def paths(self):
        """-> list over paths of [(split_index, group_index), ...]: block g's prediction in the j-th split that tests it belongs to path j,
        so every path holds exactly one out-of-sample prediction for every block (a full backtest path)"""
        combos = self.combos()
        seen = {g: 0 for g in range(self.n_groups)}
        paths = [[] for _ in range(self.n_paths())]
        for s, combo in enumerate(combos):
            for g in combo:
                paths[seen[g]].append((s, g))
                seen[g] += 1
        return paths
