import numpy as np
import pandas as pd

from stockemailer.analysis.validation import (
    build_validation_frame,
    calculate_information_coefficients,
    calculate_multicollinearity,
)


def make_market_data(seed: int) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=80, freq="D")
    values = 100 + np.cumsum(np.sin(np.arange(80) + seed) + 1.5)
    close = pd.Series(values, index=index)
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1000 + np.arange(80) * 10,
        },
        index=index,
    )


def test_build_validation_frame_contains_forward_returns_without_mutation():
    data = make_market_data(0)
    original_columns = list(data.columns)

    result = build_validation_frame([("TEST.NS", data)], (1, 5))

    assert "FORWARD_RETURN_1D" in result.columns
    assert "FORWARD_RETURN_5D" in result.columns
    assert "MA_TREND_ALIGNMENT" in result.columns
    assert list(data.columns) == original_columns
    assert len(result) == len(data)


def test_information_coefficients_are_calculated_for_indicators_and_patterns():
    validation_frame = build_validation_frame(
        [("A.NS", make_market_data(0)), ("B.NS", make_market_data(1))],
        (1, 5),
    )

    result = calculate_information_coefficients(validation_frame, (1, 5))

    assert "RETURN_2D" in result
    assert "BULLISH_ENGULFING" in result
    assert set(result["RETURN_2D"]) == {"1", "5"}
    assert result["RETURN_2D"]["1"]["observations"] > 0
    assert -1 <= result["RETURN_2D"]["1"]["ic"] <= 1


def test_multicollinearity_reports_correlated_features():
    validation_frame = build_validation_frame(
        [("A.NS", make_market_data(0)), ("B.NS", make_market_data(1))],
        (1,),
    )

    result = calculate_multicollinearity(
        validation_frame,
        correlation_threshold=0.80,
    )

    assert "MA_TREND_ALIGNMENT" in result["features"]
    assert "spearman_correlation" in result
    assert "vif" in result
    assert isinstance(result["high_correlation_pairs"], list)
