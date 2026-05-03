# utils/ml_predictor.py
# -*- coding: utf-8 -*-
import os
import pickle
import logging
import numpy as np

_logger = logging.getLogger(__name__)


class MLPredictor:
    """Singleton wrapper for the ML model."""

    _instance = None
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._load_model()

    def _load_model(self):
        try:
            module_path = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            model_path = os.path.join(
                module_path, 'ml_models',
                'best_group_performance_model.pkl'
            )

            if not os.path.exists(model_path):
                _logger.error("ML model not found: %s", model_path)
                self._model = None
                return

            with open(model_path, 'rb') as f:
                self._model = pickle.load(f)

            _logger.info("✅ ML model loaded: %s", model_path)

        except Exception as e:
            _logger.error("❌ ML model load failed: %s", str(e))
            self._model = None

    @property
    def is_loaded(self):
        return self._model is not None

    def predict(self, features):
        if not self.is_loaded:
            return None
        try:
            if isinstance(features, dict):
                arr = np.array([list(features.values())])
            elif isinstance(features, list):
                arr = np.array([features])
            else:
                arr = np.array(features).reshape(1, -1)

            result = self._model.predict(arr)

            # Convert numpy types to Python native for JSON
            prediction = result[0]
            if hasattr(prediction, 'item'):
                prediction = prediction.item()

            return prediction

        except Exception as e:
            _logger.error("Prediction failed: %s", str(e))
            return None

    def predict_proba(self, features):
        if not self.is_loaded:
            return None
        try:
            if not hasattr(self._model, 'predict_proba'):
                return None

            if isinstance(features, dict):
                arr = np.array([list(features.values())])
            elif isinstance(features, list):
                arr = np.array([features])
            else:
                arr = np.array(features).reshape(1, -1)

            return self._model.predict_proba(arr)[0].tolist()

        except Exception as e:
            _logger.error("predict_proba failed: %s", str(e))
            return None