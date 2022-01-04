# stdlib
import copy
from typing import Any, List, Optional

# third party
import lime
import numpy as np
import pandas as pd

# adjutorium absolute
from adjutorium.plugins.explainers.base import ExplainerPlugin


class LimePlugin(ExplainerPlugin):
    def __init__(
        self,
        estimator: Any,
        X: pd.DataFrame,
        y: pd.DataFrame,
        feature_names: Optional[List] = None,
        task_type: str = "classification",
        prefit: bool = False,
        n_epoch: int = 10000,
        # Treatment effects
        w: Optional[pd.DataFrame] = None,
        y_full: Optional[pd.DataFrame] = None,  # for treatment effects
        # Risk estimation
        time_to_event: Optional[pd.DataFrame] = None,  # for survival analysis
        eval_times: Optional[List] = None,  # for survival analysis
    ) -> None:
        if task_type not in ["classification", "treatments", "risk_estimation"]:
            raise RuntimeError("invalid task type")

        self.task_type = task_type
        self.feature_names = list(
            feature_names if feature_names is not None else pd.DataFrame(X).columns
        )
        super().__init__(self.feature_names)

        model = copy.deepcopy(estimator)
        if task_type == "classification":
            if not prefit:
                model.fit(X, y)
            self.predict_fn = lambda x: np.asarray(model.predict_proba(x).astype(float))
        elif task_type == "treatments":
            if w is None or y_full is None:
                raise RuntimeError("invalid input for treatments")

            if not prefit:
                model.fit(X, w, y)
            self.predict_fn = lambda x: np.asarray(model.predict(x).astype(float))
        elif task_type == "risk_estimation":
            if time_to_event is None or eval_times is None:
                raise RuntimeError("invalid input for risk estimation interpretability")

            if not prefit:
                model.fit(X, time_to_event, y)

            def model_fn(X: pd.DataFrame) -> pd.DataFrame:
                return np.asarray(model.predict(X, eval_times)).astype(float)

            self.predict_fn = model_fn

        if task_type == "classification":
            self.explainer = lime.lime_tabular.LimeTabularExplainer(
                np.asarray(X), feature_names=self.feature_names
            )
        else:
            self.explainer = lime.lime_tabular.LimeTabularExplainer(
                np.asarray(X), feature_names=self.feature_names, mode="regression"
            )

    def explain(self, X: pd.DataFrame) -> pd.DataFrame:
        X = np.asarray(X).squeeze()
        if len(X.shape) > 1:
            raise ValueError("Lime supports a single instance")
        expl = self.explainer.explain_instance(
            X,
            self.predict_fn,  # labels=self.feature_names,# top_labels=self.feature_names
        )
        importance = expl.as_list(label=1)

        vals = [x[1] for x in importance]
        cols = [x[0] for x in importance]

        return pd.DataFrame([vals], columns=cols)

    @staticmethod
    def name() -> str:
        return "lime"

    @staticmethod
    def pretty_name() -> str:
        return "LIME"


plugin = LimePlugin
