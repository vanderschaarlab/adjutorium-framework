# third party
import numpy as np
import pandas as pd

# adjutorium absolute
from adjutorium.studies._preprocessing import (
    dataframe_drop_low_variance,
    dataframe_encode,
    dataframe_encode_and_impute,
    dataframe_hash,
    dataframe_imputation,
    dataframe_preprocess,
    dataframe_remove_zeros,
    dataframe_sample,
)


def test_dataframe_hash() -> None:
    df = pd.DataFrame({"test": [0, 1, 2]})
    assert dataframe_hash(df) == "5491649331962632325"


def test_dataframe_remove_nonzero() -> None:
    df = pd.DataFrame({"test": [0, 1, 2]})

    actual = dataframe_remove_zeros(df, "test")["test"]
    expected = [1, 2]

    assert all([a == b for a, b in zip(actual, expected)])


def test_dataframe_imputation() -> None:
    df = pd.DataFrame({"test": [0, 1, 2, np.nan]})

    df, imputer = dataframe_imputation(df)

    assert not df.isnull().values.any()
    assert hasattr(imputer, "transform")


def test_dataframe_drop_low_variance() -> None:
    df = pd.DataFrame({"test": [0, 1, 2, 2], "test2": [0, 0, 0, 0]})

    df = dataframe_drop_low_variance(df)

    assert len(df.columns) == 1
    assert "test" in df.columns
    assert "test2" not in df.columns


def test_dataframe_encode() -> None:
    df = pd.DataFrame({"test": ["0", "1", np.nan], "not_encoded": ["1", "2", "3"]})

    actual, encoders = dataframe_encode(df)

    for val in ["1", "2", "3"]:
        assert "not_encoded_" + val in actual.columns

    assert "not_encoded" in encoders.encoders


def test_dataframe_encode_impute() -> None:
    df = pd.DataFrame({"test": [0, 1, np.nan], "not_encoded": ["1", "2", "3"]})

    actual, encoders = dataframe_encode_and_impute(df, imputation_method="mean")

    for val in ["1", "2", "3"]:
        assert "not_encoded_" + val in actual.columns

    assert "not_encoded" in encoders.encoders

    df = encoders.encode(df)
    assert not df.isnull().values.any()
    assert len(df.columns) == 6

    df = encoders.decode(df)
    assert "test" in df.columns
    assert "not_encoded" in df.columns

    df = encoders.encode(df)
    assert len(df.columns) == 6
    assert "not_encoded_1" in df.columns

    df = encoders.numeric_decode(df)
    assert len(df.columns) == 2


def test_dataframe_sample() -> None:
    df = pd.DataFrame(
        {"test": [0, 1, 0, 1, 0, 1], "not_encoded": ["1", "2", "3", "4", 5, 6]}
    )

    indices = dataframe_sample(df, df["test"], max_size=2)

    assert len(indices) == 4


def test_dataframe_preprocess() -> None:
    df = pd.DataFrame(
        {
            "target": [0, 1, 0, 1, 0, 1],
            "not_encoded": ["1", "2", "3", "4", "5", "6"],
            "time_to_event": [0, 1, 2, 3, 4, 5],
            "special": [0, 1, 2, 3, 4, 5],
            "nans": [1, 2, 3, np.nan, np.nan, np.nan],
            "constant": [0, 0, 0, 0, 0, 0],
        }
    )

    X, T, Y, others, enc_ctx = dataframe_preprocess(
        df,
        target="target",
        time_to_event="time_to_event",
        special_cols=["special"],
        imputation_method="mean",
    )

    assert not X.isnull().values.any()
    assert len(X.columns) == 4
    assert len(X) == 5
    assert len(others) == 1
    assert "not_encoded" in enc_ctx.encoders