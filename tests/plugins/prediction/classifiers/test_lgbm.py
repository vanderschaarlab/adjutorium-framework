# stdlib
import sys
from typing import Any

# third party
import numpy as np
import optuna
import pytest
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

# autoprognosis absolute
from autoprognosis.plugins.prediction import PredictionPlugin, Predictions
from autoprognosis.plugins.prediction.classifiers.plugin_lgbm import plugin
from autoprognosis.utils.serialization import load_model, save_model
from autoprognosis.utils.tester import evaluate_estimator


def from_api() -> PredictionPlugin:
    return Predictions().get("lgbm")


def from_module() -> PredictionPlugin:
    return plugin()


def from_serde() -> PredictionPlugin:
    buff = plugin().save()
    return plugin().load(buff)


def from_pickle() -> PredictionPlugin:
    buff = save_model(plugin())
    return load_model(buff)


@pytest.mark.parametrize(
    "test_plugin", [from_api(), from_module(), from_serde(), from_pickle()]
)
def test_lgbm_plugin_sanity(test_plugin: PredictionPlugin) -> None:
    assert test_plugin is not None


@pytest.mark.parametrize(
    "test_plugin", [from_api(), from_module(), from_serde(), from_pickle()]
)
def test_lgbm_plugin_name(test_plugin: PredictionPlugin) -> None:
    assert test_plugin.name() == "lgbm"


@pytest.mark.parametrize(
    "test_plugin", [from_api(), from_module(), from_serde(), from_pickle()]
)
def test_lgbm_plugin_type(test_plugin: PredictionPlugin) -> None:
    assert test_plugin.type() == "prediction"
    assert test_plugin.subtype() == "classifier"


@pytest.mark.parametrize(
    "test_plugin", [from_api(), from_module(), from_serde(), from_pickle()]
)
def test_lgbm_plugin_hyperparams(test_plugin: PredictionPlugin) -> None:
    assert len(test_plugin.hyperparameter_space()) == 6
    assert test_plugin.hyperparameter_space()[0].name == "reg_lambda"
    assert test_plugin.hyperparameter_space()[1].name == "reg_alpha"
    assert test_plugin.hyperparameter_space()[2].name == "colsample_bytree"
    assert test_plugin.hyperparameter_space()[3].name == "subsample"
    assert test_plugin.hyperparameter_space()[4].name == "num_leaves"
    assert test_plugin.hyperparameter_space()[5].name == "min_child_samples"


@pytest.mark.skipif(sys.platform == "darwin", reason="LGBM crash on OSX")
@pytest.mark.parametrize(
    "test_plugin", [from_api(), from_module(), from_serde(), from_pickle()]
)
def test_lgbm_plugin_fit_predict(test_plugin: PredictionPlugin) -> None:
    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    y_pred = test_plugin.fit(X_train, y_train).predict(X_test).to_numpy()

    assert np.abs(np.subtract(y_pred, y_test)).mean() < 1


@pytest.mark.skipif(sys.platform == "darwin", reason="LGBM crash on OSX")
def test_param_search() -> None:
    if len(plugin.hyperparameter_space()) == 0:
        return

    X, y = load_iris(return_X_y=True)

    def evaluate_args(**kwargs: Any) -> float:
        model = plugin(**kwargs)
        metrics = evaluate_estimator(model, X, y)

        return metrics["raw"]["aucroc"][0]

    def objective(trial: optuna.Trial) -> float:
        args = plugin.sample_hyperparameters(trial)
        return evaluate_args(**args)

    study = optuna.create_study(
        load_if_exists=True,
        directions=["maximize"],
        study_name=f"test_param_search_{plugin.name()}",
    )
    study.optimize(objective, n_trials=10, timeout=60)

    assert len(study.trials) > 0
