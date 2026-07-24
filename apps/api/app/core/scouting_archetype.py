"""PCA + k-means archetype helpers (numpy-only, no sklearn dep).

Inputs are already-z-scored matrices (rows = players, cols = metrics). Outputs:
- ``pca``: 3 principal components + loadings + explained variance ratios.
- ``kmeans``: cluster labels + silhouette score + per-cluster labels by top metrics.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def mean_impute(z: np.ndarray) -> np.ndarray:
    out = z.copy()
    for j in range(out.shape[1]):
        col = out[:, j]
        mask = np.isnan(col)
        if mask.all():
            out[:, j] = 0.0
        elif mask.any():
            out[mask, j] = float(np.nanmean(col))
    return out


def pca(z: np.ndarray, k: int = 3) -> dict[str, Any]:
    """SVD-based PCA on a z-scored matrix. Returns scores, loadings, variance ratios."""
    if z.size == 0:
        return {"scores": np.zeros((0, k)), "loadings": np.zeros((0, k)), "explained": [0.0] * k}
    x = mean_impute(z)
    x = x - x.mean(axis=0, keepdims=True)
    n, p = x.shape
    k_eff = max(1, min(k, p, n))
    u, s, vt = np.linalg.svd(x, full_matrices=False)
    scores = u[:, :k_eff] * s[:k_eff]
    loadings = vt[:k_eff].T
    total_var = float(np.sum(s ** 2)) if s.size else 1.0
    explained = [float((sv ** 2) / total_var) if total_var > 0 else 0.0 for sv in s[:k_eff]]
    # Pad to requested k.
    if k_eff < k:
        scores = np.hstack([scores, np.zeros((scores.shape[0], k - k_eff))])
        loadings = np.hstack([loadings, np.zeros((loadings.shape[0], k - k_eff))])
        explained = explained + [0.0] * (k - k_eff)
    return {"scores": scores, "loadings": loadings, "explained": explained}


def _kmeans_pp_init(x: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    n = x.shape[0]
    if n == 0 or k <= 0:
        return np.zeros((0, x.shape[1]))
    idx = [int(rng.integers(0, n))]
    centers = [x[idx[0]]]
    for _ in range(1, k):
        d2 = np.min(
            np.stack([np.sum((x - c) ** 2, axis=1) for c in centers], axis=1),
            axis=1,
        )
        total = float(np.sum(d2))
        if total <= 0:
            j = int(rng.integers(0, n))
        else:
            probs = d2 / total
            j = int(rng.choice(n, p=probs))
        idx.append(j)
        centers.append(x[j])
    return np.array(centers)


def kmeans(
    x: np.ndarray,
    *,
    k: int = 4,
    max_iter: int = 50,
    seed: int = 42,
) -> dict[str, Any]:
    if x.size == 0 or k <= 0:
        return {"labels": np.zeros(0, dtype=int), "centers": np.zeros((0, 0)), "inertia": 0.0}
    x = mean_impute(x)
    n = x.shape[0]
    k_eff = max(1, min(k, n))
    rng = np.random.default_rng(seed)
    centers = _kmeans_pp_init(x, k_eff, rng)
    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        # Assign.
        dists = np.stack([np.sum((x - c) ** 2, axis=1) for c in centers], axis=1)
        new_labels = np.argmin(dists, axis=1)
        if np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels
        # Update.
        for j in range(k_eff):
            mask = labels == j
            if mask.any():
                centers[j] = x[mask].mean(axis=0)
            else:
                centers[j] = x[int(rng.integers(0, n))]
    # Inertia.
    inertia = float(np.sum(np.min(np.stack([np.sum((x - c) ** 2, axis=1) for c in centers], axis=1), axis=1)))
    return {"labels": labels, "centers": centers, "inertia": inertia}


def silhouette(x: np.ndarray, labels: np.ndarray) -> float:
    """Mean silhouette score (subsampled for large n). Returns 0 when degenerate."""
    n = x.shape[0]
    if n < 3:
        return 0.0
    unique = np.unique(labels)
    if unique.size < 2:
        return 0.0
    # Subsample for performance.
    rng = np.random.default_rng(0)
    if n > 500:
        idx = rng.choice(n, size=500, replace=False)
        xs, ls = x[idx], labels[idx]
    else:
        xs, ls = x, labels
    m = xs.shape[0]
    s_vals = np.zeros(m)
    for i in range(m):
        same = ls == ls[i]
        same[i] = False
        if not same.any():
            continue
        a = float(np.mean(np.linalg.norm(xs[same] - xs[i], axis=1)))
        b_candidates: list[float] = []
        for lbl in unique:
            if lbl == ls[i]:
                continue
            other = ls == lbl
            if other.any():
                b_candidates.append(float(np.mean(np.linalg.norm(xs[other] - xs[i], axis=1))))
        if not b_candidates:
            continue
        b = min(b_candidates)
        denom = max(a, b)
        s_vals[i] = (b - a) / denom if denom > 0 else 0.0
    return float(np.mean(s_vals))


def cluster_labels(
    centers: np.ndarray,
    metric_names: list[str],
    *,
    top_k: int = 2,
) -> list[str]:
    """Heuristic name per cluster: 'high X, high Y' from top mean z metrics."""
    out: list[str] = []
    for i in range(centers.shape[0]):
        c = centers[i]
        order = np.argsort(-c)
        picks = [metric_names[j] for j in order[:top_k] if c[j] > 0]
        if not picks:
            order_neg = np.argsort(c)
            picks = ["low " + metric_names[j] for j in order_neg[:top_k]]
            label = ", ".join(picks)
        else:
            label = ", ".join("high " + p for p in picks)
        out.append(label)
    return out
