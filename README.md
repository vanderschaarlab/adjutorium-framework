
<h1 align="center">
  <br>
  <a href="https://www.vanderschaar-lab.com/"><img src="https://www.vanderschaar-lab.com/wp-content/uploads/2020/07/AutoML_Fig1_rev-2048x1199.png" alt="Adjutorium" width="400"></a>
  <br>
  Adjutorium
  <br>
</h1>

<h3 align="center">
  <br>
  A system for automating the design of predictive modeling pipelines tailored for clinical prognosis.
  <br>
</h3>

[![Slack](https://img.shields.io/badge/chat-on%20slack-7A5979.svg)](https://vanderschaarlab.slack.com/messages/general)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/vanderschaarlab/adjutorium-framewor/blob/main/LICENSE)

## Features

- Automatically learns ensembles of pipelines for prediction or survival analysis.
- Easy to extend pluginable architecture.
- Interpretability tools.

## Installation

#### Using pip

```bash
$ pip install .
```

### Redis (Optional, but recommended)
Adjutorium can use Redis as a backend to improve the performance and quality of the searches.

For that, install the redis-server package following the steps described on the [official site](https://redis.io/topics/quickstart).

## Testing
After installing the library, the tests can be executed using `pytest`
```bash
$ pip install .[testing]
$ pytest -vxs -m "not slow"
```
## Using the library
More advanced use cases can be found on our [tutorials section](#tutorials).

#### Example: list available classifiers
```python
from adjutorium.plugins.prediction.classifiers import Classifiers
print(Classifiers().list())
```

#### Example for classification estimators studies
```python
from pathlib import Path

from sklearn.datasets import load_breast_cancer

from adjutorium.studies.classifiers import ClassifierStudy
from adjutorium.utils.serialization import load_model_from_file
from adjutorium.utils.tester import evaluate_estimator


X, Y = load_breast_cancer(return_X_y=True, as_frame=True)

df = X.copy()
df["target"] = Y

workspace = Path("workspace")
study_name = "example"

study = ClassifierStudy(
    study_name=study_name,
    dataset=df,  # pandas DataFrame
    target="target",  # the label column in the dataset
    num_iter=2,  # how many trials to do for each candidate
    timeout=10,  # seconds
    classifiers=["logistic_regression", "lda", "qda"],
    workspace=workspace,
)

study.run()

output = workspace / study_name / "model.p"
model = load_model_from_file(output)

metrics = evaluate_estimator(model, X, Y)

print(f"model {model.name()} -> {metrics['clf']}")
```

#### Example: list available survival analysis estimators
```python
from adjutorium.plugins.prediction.risk_estimation import RiskEstimation
print(RiskEstimation().list())
```
### Example for survival analysis studies
```python
import os
from pathlib import Path

from lifelines.datasets import load_rossi

from adjutorium.studies.risk_estimation import RiskEstimationStudy
from adjutorium.utils.serialization import load_model_from_file
from adjutorium.utils.tester import evaluate_survival_estimator


rossi = load_rossi()

X = rossi.drop(["week", "arrest"], axis=1)
Y = rossi["arrest"]
T = rossi["week"]

eval_time_horizons = [
    int(T[Y.iloc[:] == 1].quantile(0.25)),
    int(T[Y.iloc[:] == 1].quantile(0.50)),
    int(T[Y.iloc[:] == 1].quantile(0.75)),
]

workspace = Path("workspace")
study_name = "example_risks"

study = RiskEstimationStudy(
    study_name=study_name,
    dataset=rossi,
    target="arrest",
    time_to_event="week",
    time_horizons=eval_time_horizons,
    num_iter=2,
    num_study_iter=1,
    timeout=10,
    risk_estimators=["cox_ph", "lognormal_aft", "loglogistic_aft"],
    workspace=workspace,
)

study.run()

output = workspace / study_name / "model.p"

if output.exists():
    model = load_model_from_file(output)

    metrics = evaluate_survival_estimator(model, X, T, Y, eval_time_horizons)

    print(f"Model {model.name()} score: {metrics['clf']}")
```
## Building a demonstrator

After running a study, a model template will be available in the workspace, in the `model.p` file.
Based on this template, you can create a demonstrator using the `scripts/build_demonstrator.py` script.

```bash
Usage: build_demonstrator.py [OPTIONS]

Options:
  --name TEXT               The title of the demonstrator
  --task_type TEXT          classification/risk_estimation
  --dataset_path TEXT       Path to the dataset csv
  --model_path TEXT         Path to the model template, usually model.p
  --time_column TEXT        Only for risk_estimation tasks. Which column in
                            the dataset is used for time-to-event
  --target_column TEXT      Which column in the dataset is the outcome
  --horizons TEXT           Only for risk_estimation tasks. Which time
                            horizons to plot.
  --explainers TEXT         Which explainers to include. There can be multiple
                            explainer names, separated by a comma. Available
                            explainers:
                            kernel_shap,invase,shap_permutation_sampler,lime.
  --imputers TEXT           Which imputer to use. Available imputers:
                            ['sinkhorn', 'EM', 'mice', 'ice', 'hyperimpute',
                            'most_frequent', 'median', 'missforest',
                            'softimpute', 'nop', 'mean', 'gain']
  --plot_alternatives TEXT  Only for risk_estimation. List of categorical
                            columns by which to split the graphs. For example,
                            plot outcome for different treatments available.
  --output TEXT             Where to save the demonstrator files. The content
                            of the folder can be directly used for
                            deployments(for example, to Heroku).
  --heroku_app TEXT         Optional. If provided, the script tries to deploy
                            the demonstrator to Heroku, to the specified
                            Heroku app name.
  --help                    Show this message and exit.
```
### Build a demonstrator for a classification task
For this task, the scripts needs access to the model template `workspace/model.p`(generated after running a study), the baseline dataset "dataset.csv", and the target column `target` in the dataset, which contains the outcomes. Based on that, the demonstrator can be built using:
```bash
python ./scripts/build_demonstrator.py \
  --model_path=workspace/model.p  \
  --dataset_path=dataset.csv \
  --target_column=target \
  --task_type=classification
```
The result is a folder, `image_bin`, containing all the files necessary for running the demonstrator.
You can start the demonstrator using
```bash
cd image_bin/
pip install -r ./requirements.txt
python ./app.py
```
The contents of the `image_bin` can be used for cloud deployments, for example, Heroku.

Optionally, you can customize the `output` option to store the output files. The default is set to `image_bin`.

### Build a demonstrator for a survival analysis task
For this task, the scripts needs access to the model template `workspace/model.p`(generated after running a study), the baseline dataset "dataset.csv", the target column `target` in the dataset, the time_to_event column `time_to_event`, and the plotted time horizons. Based on that, the demonstrator can be built using:
```bash
python ./scripts/build_demonstrator.py \
  --model_path=workspace/model.p \
  --dataset_path=dataset.csv \
  --time_column=time_to_event \
  --target_column=target \
  --horizons="14,27,41" # use your own time horizons here, separated by a comma
  --task_type=risk_estimation
```
The result is a folder, `image_bin`, containing all the files necessary for running the demonstrator.
You can start the demonstrator using
```bash
cd image_bin/
pip install -r ./requirements.txt
python ./app.py
```
The contents of the `image_bin` can be used for cloud deployments, for example, Heroku.

### Customizing the demonstrator

You can customize your demonstrator, by selected multiple explainers.
```bash
python ./scripts/build_demonstrator.py \
  --model_path=workspace/model.p  \
  --dataset_path=dataset.csv \
  --target_column=target \
  --task_type=classification
  --explainers="invase,kernel_shap"
```

### Uploading to Heroku
If you want to directly upload the demonstrator to Heroku, you will need:
 - The [`heroku` CLI tool](https://devcenter.heroku.com/articles/heroku-cli).
 - The Heroku app name you want to use. This must be the exact name you created in the Heroku dashboard.

For deploying, run:

```bash
python ./scripts/build_demonstrator.py \
  --model_path=workspace/model.p  \
  --dataset_path=dataset.csv \
  --target_column=target \
  --task_type=classification
  --heroku_app=test-adjutorium-deploy # replace with your app name
```

After the local build is done, the script will try to login to Heroku, and then upload the `image_bin` folder.

## Tutorials

### Plugins
- [Imputation ](tutorials/plugins/tutorial_00_imputer_plugins.ipynb)
- [Preprocessing](tutorial_01_preprocessing_plugins.ipynb)
- [Classification](tutorials/plugins/tutorial_02_classification_plugins.ipynb)
- [Pipelines](tutorials/plugins/tutorial_03_pipelines.ipynb)
- [Interpretability](tutorials/plugins/tutorial_04_interpretability.ipynb)
### AutoML
 - [Classification tasks](tutorials/automl/tutorial_00_classification_study.ipynb)
 - [Classification tasks with imputation](tutorials/automl/tutorial_03_automl_classification_with_imputation.ipynb)
 - [Survival analysisi tasks](tutorials/automl/tutorial_01_survival_analysis_study.ipynb)
 - [Survival analysisi tasks with imputation](tutorials/automl/tutorial_02_automl_survival_analysis_with_imputation.ipynb)

## References
1. [Adjutorium: Automated Clinical Prognostic Modeling via Bayesian Optimization with Structured Kernel Learning](https://arxiv.org/abs/1802.07207)
2. [Prognostication and Risk Factors for Cystic Fibrosis via Automated Machine Learning](https://www.nature.com/articles/s41598-018-29523-2)
3. [Cardiovascular Disease Risk Prediction using Automated Machine Learning: A Prospective Study of 423,604 UK Biobank Participants](https://www.ncbi.nlm.nih.gov/pubmed/31091238)
