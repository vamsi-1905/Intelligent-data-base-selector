"""Ranking analysis on top of catalog scores: WSM, TOPSIS, sensitivity, gaps."""

import numpy as np
import pandas as pd


def score_matrix(caps: pd.DataFrame, labels) -> pd.DataFrame:
    sub = caps[caps["criterion"].isin(labels)]
    m = sub.pivot_table(
        index="database_name", columns="criterion", values="score", aggfunc="first"
    ).astype(float)
    m = m.reindex(columns=[c for c in labels if c in m.columns])
    return m.fillna(m.mean())


def normalize_weights(importance: dict, columns) -> pd.Series:
    raw = pd.Series(
        {c: float(importance[c]) for c in columns if importance.get(c)}, dtype=float
    )
    raw = raw[raw > 0]
    if raw.empty:
        raise ValueError("At least one criterion needs an importance above zero.")
    return raw / raw.sum()


def wsm(m: pd.DataFrame, w: pd.Series) -> pd.Series:
    return (m[w.index] * w).sum(axis=1).sort_values(ascending=False)


def topsis(m: pd.DataFrame, w: pd.Series) -> pd.Series:
    x = m[w.index].astype(float)
    norm = np.sqrt((x ** 2).sum()).replace(0, 1)
    v = (x / norm) * w
    best, worst = v.max(), v.min()
    d_best = np.sqrt(((v - best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((v - worst) ** 2).sum(axis=1))
    total = (d_best + d_worst).replace(0, np.nan)
    return (d_worst / total).fillna(0.5).sort_values(ascending=False)


def contributions(m: pd.DataFrame, w: pd.Series) -> pd.DataFrame:
    return m[w.index] * w


def sensitivity(m, w, runs=500, jitter=0.3, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    arr = m[w.index].to_numpy()
    base = w.to_numpy()
    n = len(m)
    ranks = np.zeros((runs, n))
    for i in range(runs):
        ww = base * rng.uniform(1 - jitter, 1 + jitter, size=len(base))
        ww = ww / ww.sum()
        scores = arr @ ww
        ranks[i] = (-scores).argsort().argsort() + 1
    out = pd.DataFrame(
        {
            "p_first": (ranks == 1).mean(axis=0),
            "p_top3": (ranks <= 3).mean(axis=0),
            "avg_rank": ranks.mean(axis=0),
            "best_rank": ranks.min(axis=0).astype(int),
            "worst_rank": ranks.max(axis=0).astype(int),
        },
        index=m.index,
    )
    return out.sort_values(["p_first", "avg_rank"], ascending=[False, True])


def critical_gaps(m, importance, min_importance=8, max_score=5) -> dict:
    gaps = {}
    for db_name, row in m.iterrows():
        gaps[db_name] = [
            (c, float(row[c]), float(importance[c]))
            for c in m.columns
            if importance.get(c) and importance[c] >= min_importance and row[c] <= max_score
        ]
    return gaps


def analyze(caps: pd.DataFrame, importance: dict, runs=500) -> dict:
    labels = [c for c, v in importance.items() if v]
    if not labels:
        raise ValueError("No requirements with an importance above zero.")
    m = score_matrix(caps, labels)
    if m.empty:
        raise ValueError("No catalog scores match these requirements.")
    w = normalize_weights(importance, m.columns)
    return {
        "matrix": m[w.index],
        "weights": w,
        "wsm": wsm(m, w),
        "topsis": topsis(m, w),
        "sensitivity": sensitivity(m, w, runs=runs),
        "gaps": critical_gaps(m, importance),
    }