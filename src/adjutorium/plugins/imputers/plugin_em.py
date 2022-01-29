# stdlib
from typing import Any, List

# adjutorium absolute
import adjutorium.plugins.core.params as params
import adjutorium.plugins.imputers.base as base
from adjutorium.utils.pip import install

for retry in range(2):
    try:
        # third party
        from hyperimpute.plugins.imputers.plugin_em import plugin as base_model

        break
    except ImportError:
        depends = ["hyperimpute"]
        install(depends)


class EMPlugin(base.ImputerPlugin):
    """Imputation plugin for completing missing values using the EM strategy.

    Method:
        Details in the EM class implementation.

    Example:
        >>> import numpy as np
        >>> from adjutorium.plugins.imputers import Imputers
        >>> plugin = Imputers().get("EM")
        >>> plugin.fit_transform([[1, 1, 1, 1], [np.nan, np.nan, np.nan, np.nan], [1, 2, 2, 1], [2, 2, 2, 2]])
                  0         1         2         3
        0  1.000000  1.000000  1.000000  1.000000
        1  1.333333  1.666667  1.666667  1.333333
        2  1.000000  2.000000  2.000000  1.000000
        3  2.000000  2.000000  2.000000  2.000000
    """

    def __init__(self, **kwargs: Any) -> None:
        model = base_model(**kwargs)

        super().__init__(model)

    @staticmethod
    def name() -> str:
        return base_model.name()

    @staticmethod
    def hyperparameter_space(*args: Any, **kwargs: Any) -> List[params.Params]:
        return base_model.hyperparameter_space()


plugin = EMPlugin
