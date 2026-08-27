import math

import pandas as pd
import pytest

from stockemailer.analysis.price_targets import calculate_price_range


def make_close_frame(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": values})


def test_calculate_price_range_projects_from_recent_log_volatility():
    close_values = [100 * math.exp(0.01 * math.sin(index)) for index in range(30)]
    frame = make_close_frame(close_values)

    result = calculate_price_range(frame)

    log_buy_distance = math.log(
        result["last_close"] / result["buy_zone_low"]
    )
    log_sell_distance = math.log(
        result["sell_target_high"] / result["last_close"]
    )

    assert result["sell_target_high"] > result["last_close"] > result["buy_zone_low"]
    assert log_buy_distance == pytest.approx(log_sell_distance * 0.5, rel=0.02)
    assert result["buy_zone_high"] == result["last_close"]
    assert result["sell_target_low"] == result["last_close"]
    assert result["method"] == "historical_volatility_normal_approx"


def test_calculate_price_range_rejects_fewer_than_ten_valid_closes():
    frame = make_close_frame([100, 101, 102, 103, 104, 105, 106, 107, 108])

    with pytest.raises(ValueError, match="At least 10 valid Close values"):
        calculate_price_range(frame)


def test_calculate_price_range_rejects_missing_close_column():
    frame = pd.DataFrame({"Open": [100] * 10})

    with pytest.raises(ValueError, match="Close column is required"):
        calculate_price_range(frame)


def test_higher_confidence_and_longer_horizon_widen_the_range():
    close_values = [100 * math.exp(0.02 * math.sin(index)) for index in range(30)]
    frame = make_close_frame(close_values)

    standard = calculate_price_range(frame, horizon_days=5, confidence=0.90)
    higher_confidence = calculate_price_range(
        frame,
        horizon_days=5,
        confidence=0.99,
    )
    longer_horizon = calculate_price_range(
        frame,
        horizon_days=10,
        confidence=0.90,
    )

    assert higher_confidence["buy_zone_low"] < standard["buy_zone_low"]
    assert higher_confidence["sell_target_high"] > standard["sell_target_high"]
    assert longer_horizon["buy_zone_low"] < standard["buy_zone_low"]
    assert longer_horizon["sell_target_high"] > standard["sell_target_high"]
