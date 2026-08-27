import json

import numpy as np
import pandas as pd

from stockemailer.backtesting import run_backtest_range


def make_market_data() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=270, freq="D")
    close = pd.Series(100 + np.arange(270) * 0.1, index=index)
    close.loc[pd.Timestamp("2024-09-16")] = 125
    close.loc[pd.Timestamp("2024-09-17")] = 126
    frame = pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1000,
        },
        index=index,
    )
    frame.loc[pd.Timestamp("2024-09-17"), "Open"] = 125
    frame.loc[pd.Timestamp("2024-09-17"), "Low"] = 120
    frame.loc[pd.Timestamp("2024-09-17"), "High"] = 135
    return frame


def test_run_backtest_range_writes_daily_and_consolidated_results(tmp_path):
    calls = []

    def loader(ticker: str, start: str, end: str, interval: str):
        calls.append((ticker, start, end, interval))
        return make_market_data()

    result = run_backtest_range(
        "2024-09-16",
        "2024-09-17",
        output_dir=tmp_path,
        tickers=["TEST.NS"],
        data_loader=loader,
    )

    assert result["start_date"] == "2024-09-16"
    assert result["end_date"] == "2024-09-17"
    assert result["dates_processed"] == 2
    assert len(result["daily_results"]) == 2
    assert result["trades_evaluated"] == sum(
        daily["trades_evaluated"] for daily in result["daily_results"]
    )
    assert result["successful_trades"] == sum(
        daily["successful_trades"] for daily in result["daily_results"]
    )
    assert result["success_rate_pct"] is not None
    assert len(calls) == 2
    assert all(call[3] == "15m" for call in calls)
    assert (tmp_path / "backtest_2024-09-16.json").exists()
    assert (tmp_path / "backtest_2024-09-17.json").exists()

    consolidated_path = tmp_path / "backtest_2024-09-16_to_2024-09-17.json"
    assert consolidated_path.exists()
    saved = json.loads(consolidated_path.read_text())
    assert saved["dates_processed"] == 2
