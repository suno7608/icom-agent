"""
ICOM Agent - Demand Prediction Model (S0-4)
XGBoost 기반 수요 예측 모델

PRD 5.1 Phase 0: 예측 모델 프로토타입
  - DemandPredictor 클래스
  - train / predict / evaluate
  - MAPE 20% 이내 목표
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
import joblib
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error, r2_score

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

from demand_predictor.features import FEATURE_COLUMNS, TARGET_COLUMN

logger = logging.getLogger(__name__)


class DemandPredictor:
    """
    XGBoost-based demand prediction model.

    Predicts final sales count based on early social engagement metrics
    and influencer/product features.
    """

    def __init__(self, model_dir: str = "./models", version: str = None):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.version = version or datetime.now().strftime("v%Y%m%d_%H%M%S")
        self.model = None
        self.feature_columns = FEATURE_COLUMNS
        self.metrics = {}

    def train(self, df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42) -> dict:
        """
        Train the XGBoost model.

        Args:
            df: Feature DataFrame with FEATURE_COLUMNS + TARGET_COLUMN
            test_size: Fraction of data for validation
            random_state: Random seed for reproducibility

        Returns:
            dict of evaluation metrics
        """
        if XGBRegressor is None:
            raise ImportError("xgboost is not installed. Run: pip install xgboost")

        X = df[self.feature_columns].copy()
        y = df[TARGET_COLUMN].copy()

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        # XGBoost model
        self.model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=random_state,
            verbosity=0,
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # Evaluate
        y_pred = self.model.predict(X_test)
        y_pred = np.maximum(y_pred, 0)  # Sales can't be negative

        self.metrics = self.evaluate(y_test, y_pred)

        # Cross-validation
        cv_scores = cross_val_score(
            self.model, X, y, cv=5, scoring="neg_mean_absolute_percentage_error"
        )
        self.metrics["cv_mape_mean"] = round(-cv_scores.mean() * 100, 2)
        self.metrics["cv_mape_std"] = round(cv_scores.std() * 100, 2)

        # Feature importance
        importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        self.metrics["top_features"] = dict(
            sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
        )

        logger.info(f"Model trained - MAPE: {self.metrics['mape']:.1f}%, R²: {self.metrics['r2']:.3f}")
        return self.metrics

    @staticmethod
    def evaluate(y_true, y_pred) -> dict:
        """Calculate evaluation metrics."""
        # Filter out zero actuals for MAPE calculation
        mask = y_true > 0
        y_true_nz = y_true[mask] if hasattr(y_true, '__getitem__') else y_true
        y_pred_nz = y_pred[mask] if hasattr(y_pred, '__getitem__') else y_pred

        mape = mean_absolute_percentage_error(y_true_nz, y_pred_nz) * 100
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)

        return {
            "mape": round(mape, 2),
            "mae": round(mae, 2),
            "r2": round(r2, 4),
            "n_samples": len(y_true),
        }

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict sales for given feature data.

        Returns DataFrame with predicted_sales and confidence interval.
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() or load() first.")

        X = df[self.feature_columns].copy()
        predictions = self.model.predict(X)
        predictions = np.maximum(predictions, 0).astype(int)

        # Simple confidence interval based on training error
        mape_decimal = self.metrics.get("mape", 20) / 100
        lower = (predictions * (1 - mape_decimal)).astype(int)
        upper = (predictions * (1 + mape_decimal)).astype(int)

        result = df[["campaign_id"]].copy() if "campaign_id" in df.columns else pd.DataFrame()
        result["predicted_sales"] = predictions
        result["confidence_lower"] = np.maximum(lower, 0)
        result["confidence_upper"] = upper

        # Recommended action based on predicted sales
        result["recommended_action"] = result["predicted_sales"].apply(
            lambda x: "boost" if x >= 200 else ("hold" if x >= 50 else "stop")
        )

        return result

    def save(self) -> str:
        """Save model to disk."""
        if self.model is None:
            raise ValueError("No model to save")

        path = self.model_dir / f"demand_model_{self.version}.joblib"
        joblib.dump({
            "model": self.model,
            "version": self.version,
            "feature_columns": self.feature_columns,
            "metrics": self.metrics,
        }, path)
        logger.info(f"Model saved to {path}")
        return str(path)

    def load(self, path: str = None) -> None:
        """Load model from disk."""
        if path is None:
            # Load latest model
            models = sorted(self.model_dir.glob("demand_model_*.joblib"))
            if not models:
                raise FileNotFoundError("No saved models found")
            path = str(models[-1])

        data = joblib.load(path)
        self.model = data["model"]
        self.version = data["version"]
        self.feature_columns = data["feature_columns"]
        self.metrics = data["metrics"]
        logger.info(f"Model loaded: {self.version} (MAPE: {self.metrics.get('mape', 'N/A')}%)")
