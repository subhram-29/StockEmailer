import json

import numpy as np
import pandas as pd

import stockemailer.backtesting as backtesting
from stockemailer.backtesting import run_backtest
from stockemailer.analysis.screener import calculate_momentum_score


def make_market_data(
    analysis_date: str,
    next_open: float,
    next_close: float,
    next_high: float,
) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=270, freq="D")
    close = pd.Series(100 + np.arange(270) * 0.1, index=index)
    close.loc[pd.Timestamp(analysis_date)] = 125
    daily_frame = pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1000,
        },
        index=index,
    )
    next_day = pd.Timestamp("2024-09-17")
    intraday_index = pd.date_range(next_day + pd.Timedelta(hours=9), periods=3, freq="15min")
    intraday_frame = pd.DataFrame(
        {
            "Open": [next_open, next_open, next_close],
            "High": [next_open + 1, next_high, next_close + 1],
            "Low": [next_open - 1, next_open - 1, next_close - 1],
            "Close": [next_open, next_open, next_close],
            "Volume": [1000, 1000, 1000],
        },
        index=intraday_index,
    )
    return pd.concat([daily_frame, intraday_frame])


def test_run_backtest_selects_top_five_evaluates_next_day_and_writes_json(tmp_path):
    analysis_date = "2024-09-16"
    calls = []

    def loader(ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
        calls.append((ticker, start, end, interval))
        return make_market_data(analysis_date, 125, 126, 135)

    output_path = tmp_path / "results.json"
    result = run_backtest(
        analysis_date,
        output_path=output_path,
        tickers=[f"TEST{index}.NS" for index in range(7)],
        data_loader=loader,
    )

    assert result["analysis_date"] == analysis_date
    assert result["data_interval"] == "15m"
    assert result["entry_rule"].startswith("first 15-minute bar")
    assert result["exit_rule"].startswith("later 15-minute bar")
    assert result["stocks_selected"] == 5
    assert result["trades_evaluated"] == 5
    assert result["successful_trades"] == 5
    assert result["failed_trades"] == 0
    assert result["neutral_trades"] == 0
    assert result["unavailable_trades"] == 0
    assert all(trade["entry_possible"] for trade in result["trades"])
    assert all(trade["exit_possible"] for trade in result["trades"])
    assert all(
        trade["entry_time"] < trade["exit_time"]
        for trade in result["trades"]
    )
    assert all(trade["planned_entry_price"] is not None for trade in result["trades"])
    assert all(trade["planned_exit_price"] is not None for trade in result["trades"])
    assert all("score_components" in trade for trade in result["trades"])
    assert all("indicator_snapshot" in trade for trade in result["trades"])
    assert all("pattern_snapshot" in trade for trade in result["trades"])
    assert all(
        round(sum(trade["score_components"].values()), 2)
        == trade["momentum_score"]
        for trade in result["trades"]
    )
    assert all(
        trade["planned_exit_price"]
        <= trade["planned_entry_price"] * 1.005
        for trade in result["trades"]
    )
    assert all(trade["next_trading_date"] == "2024-09-17" for trade in result["trades"])
    assert all(call[1] == "2024-07-20" for call in calls)
    assert all(call[2] == "2024-09-19" for call in calls)
    assert all(call[3] == "15m" for call in calls)

    saved_result = json.loads(output_path.read_text())
    assert saved_result["successful_trades"] == 5
    assert len(saved_result["trades"]) == 5


def test_run_backtest_counts_a_non_increasing_next_close_as_failure(tmp_path):
    analysis_date = "2024-09-16"

    result = run_backtest(
        analysis_date,
        output_path=tmp_path / "results.json",
        tickers=["TEST.NS"],
        data_loader=lambda ticker, start, end, interval: make_market_data(
            analysis_date,
            125,
            123,
            125,
        ),
    )

    assert result["trades_evaluated"] == 1
    assert result["successful_trades"] == 0
    assert result["failed_trades"] == 1
    assert result["trades"][0]["entry_possible"] is True
    assert result["trades"][0]["exit_possible"] is False


def test_run_backtest_caps_exit_midpoint_at_half_percent_above_entry(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        backtesting,
        "calculate_price_range",
        lambda data: {
            "buy_zone_low": 100.0,
            "buy_zone_high": 110.0,
            "sell_target_low": 110.0,
            "sell_target_high": 150.0,
        },
    )

    result = run_backtest(
        "2024-09-16",
        output_path=tmp_path / "results.json",
        tickers=["TEST.NS"],
        data_loader=lambda ticker, start, end, interval: make_market_data(
            "2024-09-16",
            105,
            106,
            111,
        ),
    )

    trade = result["trades"][0]
    assert trade["planned_entry_price"] == 105.0
    assert trade["planned_exit_price"] == 105.52
    assert trade["exit_possible"] is True


def test_run_backtest_rejects_invalid_date():
    try:
        run_backtest("16-09-2024", output_path="unused.json", tickers=[])
    except ValueError as exc:
        assert "YYYY-MM-DD" in str(exc)
    else:
        raise AssertionError("Expected invalid date to raise ValueError")


def test_extended_indicators_and_patterns_affect_momentum_score():
    values = {
        "RETURN_2D": 0,
        "VOLUME_RATIO": 1,
        "RSI": 50,
        "Close": 100,
        "SMA_20": 100,
        "SMA_50": 100,
        "MACD": 0,
        "MACD_SIGNAL": 0,
        "RETURN_5D": 0,
        "ATR_14": 1,
        "BOLL_UPPER": 110,
        "BOLL_MIDDLE": 99,
        "BOLL_LOWER": 90,
        "BOLL_WIDTH": 5,
        "ADX_14": 25,
        "PLUS_DI": 20,
        "MINUS_DI": 10,
        "STOCH_K": 60,
        "STOCH_D": 50,
        "CCI_20": 50,
        "WILLIAMS_R": -40,
        "OBV": 100,
        "OBV_SLOPE_5": 1,
        "VWAP_20": 95,
        "ROC_10": 2,
        "BULLISH_ENGULFING": True,
        "BEARISH_ENGULFING": False,
        "HAMMER": True,
        "SHOOTING_STAR": False,
        "DOJI": False,
        "THREE_WHITE_SOLDIERS": True,
        "GOLDEN_CROSS": True,
        "DEATH_CROSS": False,
    }
    bullish_score = calculate_momentum_score(pd.Series(values))
    bearish_values = {
        **values,
        "ATR_14": 10,
        "BOLL_UPPER": 90,
        "BOLL_MIDDLE": 110,
        "BOLL_LOWER": 80,
        "BOLL_WIDTH": 20,
        "PLUS_DI": 10,
        "MINUS_DI": 20,
        "STOCH_K": 40,
        "STOCH_D": 50,
        "CCI_20": -50,
        "WILLIAMS_R": -60,
        "OBV": -100,
        "OBV_SLOPE_5": -1,
        "VWAP_20": 105,
        "ROC_10": -2,
        "BULLISH_ENGULFING": False,
        "BEARISH_ENGULFING": True,
        "HAMMER": False,
        "SHOOTING_STAR": True,
        "DOJI": True,
        "THREE_WHITE_SOLDIERS": False,
        "GOLDEN_CROSS": False,
        "DEATH_CROSS": True,
    }

    assert bullish_score > calculate_momentum_score(pd.Series(bearish_values))
