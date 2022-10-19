# stdlib
import copy
from typing import List, Tuple

# third party
import numpy as np
import optuna
import pandas as pd
from sklearn.model_selection import StratifiedKFold

# autoprognosis absolute
from autoprognosis.exceptions import StudyCancelled
from autoprognosis.explorers.core.defaults import (
    default_classifiers_names,
    default_feature_scaling_names,
)
from autoprognosis.explorers.core.optimizer import EarlyStoppingExceeded, create_study
from autoprognosis.explorers.hooks import DefaultHooks
from autoprognosis.hooks import Hooks
import autoprognosis.logger as log
from autoprognosis.plugins.ensemble.classifiers import (
    AggregatingEnsemble,
    BaseEnsemble,
    StackingEnsemble,
    WeightedEnsemble,
)
from autoprognosis.utils.tester import evaluate_estimator

# autoprognosis relative
from .classifiers import ClassifierSeeker

EPS = 1e-8


class EnsembleSeeker:
    """
    AutoML core logic for classification ensemble search.

    Args:
        study_name: str.
            Study ID, used for caching keys.
        num_iter: int.
            Number of optimization trials.
        num_ensemble_iter: int.
            Number of optimization trials for the ensemble weights.
        timeout: int.
            Max wait time(in seconds) for the optimization output.
        CV: int.
            Number of folds to use for evaluation
        ensemble_size: int.
            Number of base models for the ensemble.
        metric: str.
            The metric to use for optimization. ["aucroc", "aucprc"]
        feature_scaling: list.
            Plugins to use in the pipeline for preprocessing.
        classifiers: list.
            Plugins to use in the pipeline for prediction.
        imputers: list.
            Plugins to use in the pipeline for imputation.
        hooks: Hooks.
            Custom callbacks to be notified about the search progress.
    """

    def __init__(
        self,
        study_name: str,
        num_iter: int = 100,
        num_ensemble_iter: int = 100,
        timeout: int = 360,
        CV: int = 5,
        ensemble_size: int = 3,
        metric: str = "aucroc",
        feature_scaling: List[str] = default_feature_scaling_names,
        classifiers: List[str] = default_classifiers_names,
        imputers: List[str] = [],
        hooks: Hooks = DefaultHooks(),
    ) -> None:
        self.num_iter = num_ensemble_iter
        self.timeout = timeout
        self.ensemble_size = ensemble_size
        self.CV = CV
        self.metric = metric
        self.study_name = study_name
        self.hooks = hooks

        self.seeker = ClassifierSeeker(
            study_name,
            num_iter=num_iter,
            metric=metric,
            CV=CV,
            top_k=ensemble_size,
            timeout=timeout,
            feature_scaling=feature_scaling,
            classifiers=classifiers,
            hooks=hooks,
            imputers=imputers,
        )

    def _should_continue(self) -> None:
        if self.hooks.cancel():
            raise StudyCancelled("Classifier combo search cancelled")

    def pretrain_for_cv(
        self,
        ensemble: List,
        X: pd.DataFrame,
        Y: pd.DataFrame,
        seed: int = 0,
    ) -> List:
        self._should_continue()

        skf = StratifiedKFold(n_splits=self.CV, shuffle=True, random_state=seed)

        folds = []
        for train_index, _ in skf.split(X, Y):
            X_train = X.loc[X.index[train_index]]
            Y_train = Y.loc[Y.index[train_index]]

            local_fold = []
            for estimator in ensemble:
                model = copy.deepcopy(estimator)
                model.fit(X_train, Y_train)
                local_fold.append(model)
            folds.append(local_fold)
        return folds

    def search_weights(
        self,
        ensemble: List,
        X: pd.DataFrame,
        Y: pd.DataFrame,
    ) -> Tuple[WeightedEnsemble, float]:
        self._should_continue()

        study, pruner = create_study(
            load_if_exists=False,
            storage_type="none",
            study_name=f"{self.study_name}_classifier_exploration_ensemble_v2",
        )

        pretrained_models = self.pretrain_for_cv(ensemble, X, Y)

        def objective(trial: optuna.Trial) -> float:
            self._should_continue()

            weights = [
                trial.suggest_int(f"weight_{idx}", 0, 10)
                for idx in range(len(ensemble))
            ]
            pruner.check_trial(trial)

            weights = weights / (np.sum(weights) + EPS)

            folds = []
            for fold in pretrained_models:
                folds.append(WeightedEnsemble(fold, weights))

            metrics = evaluate_estimator(folds, X, Y, self.CV, pretrained=True)

            log.debug(f"ensemble {folds[0].name()} : results {metrics['clf']}")
            score = metrics["clf"][self.metric][0]

            pruner.report_score(score)

            return score

        initial_trials = []

        trial_template = {}
        for idx in range(len(ensemble)):
            trial_template[f"weight_{idx}"] = 0

        for idx in range(len(ensemble)):
            local_trial = copy.deepcopy(trial_template)
            local_trial[f"weight_{idx}"] = 1
            initial_trials.append(local_trial)

        for trial in initial_trials:
            study.enqueue_trial(trial)

        try:
            study.optimize(objective, n_trials=self.num_iter, timeout=self.timeout)
        except EarlyStoppingExceeded:
            log.info("Early stopping triggered for search")

        weights = []
        for idx in range(len(ensemble)):
            weights.append(study.best_trial.params[f"weight_{idx}"])

        weights = weights / (np.sum(weights) + EPS)
        log.info(f"Best trial for ensemble: {study.best_value} for {weights}")

        return WeightedEnsemble(ensemble, weights), study.best_value

    def search(self, X: pd.DataFrame, Y: pd.DataFrame) -> BaseEnsemble:
        self._should_continue()

        best_models = self.seeker.search(X, Y)

        if self.hooks.cancel():
            raise StudyCancelled("Classifier search cancelled")

        scores = []
        ensembles: list = []

        try:
            stacking_ensemble = StackingEnsemble(best_models)
            stacking_ens_score = evaluate_estimator(stacking_ensemble, X, Y, self.CV)[
                "clf"
            ][self.metric][0]
            log.info(
                f"Stacking ensemble: {stacking_ensemble.name()} --> {stacking_ens_score}"
            )
            scores.append(stacking_ens_score)
            ensembles.append(stacking_ensemble)
        except BaseException as e:
            log.info(f"StackingEnsemble failed {e}")

        if self.hooks.cancel():
            raise StudyCancelled("Classifier search cancelled")

        try:
            aggr_ensemble = AggregatingEnsemble(best_models)
            aggr_ens_score = evaluate_estimator(aggr_ensemble, X, Y, self.CV)["clf"][
                self.metric
            ][0]
            log.info(
                f"Aggregating ensemble: {aggr_ensemble.name()} --> {aggr_ens_score}"
            )

            scores.append(aggr_ens_score)
            ensembles.append(aggr_ensemble)
        except BaseException as e:
            log.info(f"AggregatingEnsemble failed {e}")

        if self.hooks.cancel():
            raise StudyCancelled("Classifier search cancelled")

        weighted_ensemble, weighted_ens_score = self.search_weights(best_models, X, Y)
        log.info(
            f"Weighted ensemble: {weighted_ensemble.name()} -> {weighted_ens_score}"
        )

        scores.append(weighted_ens_score)
        ensembles.append(weighted_ensemble)

        return ensembles[np.argmax(scores)]
