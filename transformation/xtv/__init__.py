"""xTV baseline package — training helpers for §4.1 snapshot model."""

from transformation.xtv.baseline import (
    AREA_INDEX_FEATURES,
    BASELINE_FEATURE_ORDER,
    TM_MV_COL,
    XTV_COLUMN,
    build_xy_training,
    fit_baseline,
    parquet_feature_matrix,
    predict_xtv_parquet,
    sklearn_baseline_pipeline,
    temporal_train_val_masks,
)

__all__ = [
    "AREA_INDEX_FEATURES",
    "BASELINE_FEATURE_ORDER",
    "TM_MV_COL",
    "XTV_COLUMN",
    "build_xy_training",
    "fit_baseline",
    "parquet_feature_matrix",
    "predict_xtv_parquet",
    "sklearn_baseline_pipeline",
    "temporal_train_val_masks",
]
