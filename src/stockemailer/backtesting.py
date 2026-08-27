import json
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from stockemailer.analysis.indicators import calculate_extended_indicators
from stockemailer.analysis.patterns import detect_patterns
from stockemailer.analysis.price_targets import calculate_price_range
from stockemailer.analysis.screener import (
    calculate_momentum_score,
    calculate_score_components,
)
from stockemailer.data.market_data import get_stock_history_between
from stockemailer.data.universe import NSE_STOCKS


DataLoader = Callable[[str, str, str, str], pd.DataFrame | None]
INTRADAY_LOOKBACK_DAYS = 58


def _parse_analysis_date(analysis_date: str) -> date:
    """Parse an ISO date and raise a clear error for invalid input."""

    try:
        return date.fromisoformat(analysis_date)
    except ValueError as exc:
        raise ValueError(
            "analysis_date must use YYYY-MM-DD format"
        ) from exc


def _datetime_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Return a timezone-naive DatetimeIndex for timestamp comparisons."""

    index = pd.to_datetime(df.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    return index


def _date_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Return a timezone-naive DatetimeIndex normalized to calendar dates."""

    return _datetime_index(df).normalize()


def _historical_analysis(
    ticker: str,
    data: pd.DataFrame,
    analysis_date: date,
) -> dict | None:
    """Calculate a stock's signals using only bars through analysis_date."""

    historical_data = data.copy()
    historical_data.index = _datetime_index(historical_data)
    historical_data = historical_data[
        historical_data.index.date <= analysis_date
    ]

    if len(historical_data) < 50:
        return None

    historical_data = detect_patterns(
        calculate_extended_indicators(historical_data)
    )
    latest = historical_data.iloc[-1]
    required_columns = [
        "RETURN_2D",
        "RETURN_5D",
        "RSI",
        "VOLUME_RATIO",
        "SMA_20",
        "SMA_50",
        "MACD",
        "MACD_SIGNAL",
    ]

    if latest[required_columns].isna().any():
        return None

    try:
        price_range = calculate_price_range(historical_data)
    except ValueError:
        price_range = None

    return {
        "ticker": ticker,
        "analysis_date": historical_data.index[-1].strftime("%Y-%m-%d"),
        "entry_price": round(float(latest["Close"]), 2),
        "momentum_score": calculate_momentum_score(latest),
        "score_components": calculate_score_components(latest),
        "indicator_snapshot": {
            name: round(float(latest[name]), 6)
            for name in (
                "RETURN_2D", "RETURN_5D", "VOLUME_RATIO", "RSI",
                "SMA_20", "SMA_50", "MACD", "MACD_SIGNAL", "ATR_14",
                "BOLL_WIDTH", "ADX_14", "PLUS_DI", "MINUS_DI", "STOCH_K",
                "STOCH_D", "CCI_20", "WILLIAMS_R", "OBV_SLOPE_5", "VWAP_20",
                "ROC_10",
            )
        },
        "pattern_snapshot": {
            name: bool(latest[name])
            for name in (
                "BULLISH_ENGULFING", "BEARISH_ENGULFING", "HAMMER",
                "SHOOTING_STAR", "DOJI", "THREE_WHITE_SOLDIERS",
                "GOLDEN_CROSS", "DEATH_CROSS",
            )
        },
        "price_range": price_range,
    }


def _next_trading_day_result(
    analysis: dict,
    data: pd.DataFrame,
) -> dict:
    """Evaluate chronological midpoint touches on the next trading day."""

    price_range = analysis["price_range"]
    planned_entry_price = (
        round(
            (
                price_range["buy_zone_low"]
                + price_range["buy_zone_high"]
            ) / 2,
            2,
        )
        if price_range
        else None
    )
    raw_planned_exit_price = (
        (
            price_range["sell_target_low"]
            + price_range["sell_target_high"]
        ) / 2
        if price_range
        else None
    )
    planned_exit_price = (
        round(
            min(
                raw_planned_exit_price,
                planned_entry_price * 1.005,
            ),
            2,
        )
        if raw_planned_exit_price is not None
        else None
    )

    indexed_data = data.copy()
    indexed_data.index = _datetime_index(indexed_data)
    later_data = indexed_data[
        indexed_data.index.date > pd.Timestamp(analysis["analysis_date"]).date()
    ]
    next_day = (
        later_data.index.normalize().min()
        if not later_data.empty
        else None
    )
    next_rows = (
        later_data[later_data.index.normalize() == next_day]
        if next_day is not None
        else later_data
    )

    if next_rows.empty:
        return {
            "ticker": analysis["ticker"],
            "analysis_date": analysis["analysis_date"],
            "momentum_score": analysis["momentum_score"],
            "score_components": analysis["score_components"],
            "indicator_snapshot": analysis["indicator_snapshot"],
            "pattern_snapshot": analysis["pattern_snapshot"],
            "planned_entry_price": planned_entry_price,
            "planned_exit_price": planned_exit_price,
            "status": "next_trading_day_unavailable",
            "entry_possible": None,
            "exit_possible": None,
        }

    entry_rows = next_rows[
        (next_rows["Low"] <= planned_entry_price)
        & (next_rows["High"] >= planned_entry_price)
    ] if planned_entry_price is not None else next_rows.iloc[0:0]

    if entry_rows.empty:
        return {
            "ticker": analysis["ticker"],
            "analysis_date": analysis["analysis_date"],
            "next_trading_date": next_day.strftime("%Y-%m-%d"),
            "momentum_score": analysis["momentum_score"],
            "score_components": analysis["score_components"],
            "indicator_snapshot": analysis["indicator_snapshot"],
            "pattern_snapshot": analysis["pattern_snapshot"],
            "planned_entry_price": planned_entry_price,
            "planned_exit_price": planned_exit_price,
            "entry_possible": False,
            "exit_possible": False,
            "status": "neutral",
        }

    entry_timestamp = entry_rows.index[0]
    exit_rows = next_rows[
        (next_rows.index > entry_timestamp)
        & (next_rows["High"] >= planned_exit_price)
    ] if planned_exit_price is not None else next_rows.iloc[0:0]
    entry_row = entry_rows.iloc[0]

    if exit_rows.empty:
        return {
            "ticker": analysis["ticker"],
            "analysis_date": analysis["analysis_date"],
            "next_trading_date": next_day.strftime("%Y-%m-%d"),
            "momentum_score": analysis["momentum_score"],
            "score_components": analysis["score_components"],
            "indicator_snapshot": analysis["indicator_snapshot"],
            "pattern_snapshot": analysis["pattern_snapshot"],
            "planned_entry_price": planned_entry_price,
            "planned_exit_price": planned_exit_price,
            "entry_time": entry_timestamp.isoformat(),
            "entry_actual": {
                "open": round(float(entry_row["Open"]), 2),
                "high": round(float(entry_row["High"]), 2),
                "low": round(float(entry_row["Low"]), 2),
                "close": round(float(entry_row["Close"]), 2),
            },
            "entry_possible": True,
            "exit_possible": False,
            "status": "failed",
        }

    exit_timestamp = exit_rows.index[0]
    exit_row = exit_rows.iloc[0]

    return {
        "ticker": analysis["ticker"],
        "analysis_date": analysis["analysis_date"],
        "next_trading_date": next_day.strftime("%Y-%m-%d"),
        "momentum_score": analysis["momentum_score"],
        "score_components": analysis["score_components"],
        "indicator_snapshot": analysis["indicator_snapshot"],
        "pattern_snapshot": analysis["pattern_snapshot"],
        "planned_entry_price": planned_entry_price,
        "planned_exit_price": planned_exit_price,
        "entry_time": entry_timestamp.isoformat(),
        "exit_time": exit_timestamp.isoformat(),
        "actual": {
            "entry_price": planned_entry_price,
            "exit_price": planned_exit_price,
            "entry_bar_close": round(float(entry_row["Close"]), 2),
            "exit_bar_high": round(float(exit_row["High"]), 2),
        },
        "entry_possible": True,
        "exit_possible": True,
        "status": "successful",
    }


def run_backtest(
    analysis_date: str,
    output_path: str | Path | None = None,
    tickers: list[str] | None = None,
    data_loader: DataLoader = get_stock_history_between,
) -> dict:
    """Backtest the top five stocks selected after a specified analysis date.

    The selection uses only historical bars available through ``analysis_date``.
    The first subsequent trading day is compared with the plan created after
    the analysis date using 15-minute bars. Entry is possible at the first bar
    touching the planned entry midpoint; exit is possible only at a later bar
    touching the planned exit midpoint. Results are written as JSON when
    ``output_path`` is provided; otherwise the default is
    ``backtest_results/backtest_<analysis_date>.json``.
    """

    parsed_date = _parse_analysis_date(analysis_date)
    selected_tickers = tickers if tickers is not None else NSE_STOCKS
    # Yahoo Finance only provides a limited recent window for 15-minute data.
    latest_allowed_start = date.today() - timedelta(
        days=INTRADAY_LOOKBACK_DAYS
    )
    if data_loader is get_stock_history_between and parsed_date < latest_allowed_start:
        raise ValueError(
            "15-minute Yahoo Finance data is only available for the most "
            f"recent {INTRADAY_LOOKBACK_DAYS} days. Analysis date "
            f"{parsed_date.isoformat()} is too old; use daily data or a "
            "stored intraday data source for older backtests."
        )

    fetch_start = parsed_date - timedelta(days=INTRADAY_LOOKBACK_DAYS)
    if data_loader is get_stock_history_between:
        fetch_start = max(fetch_start, latest_allowed_start)
    fetch_end = parsed_date + timedelta(days=3)
    loaded_data: dict[str, pd.DataFrame] = {}
    analyses = []

    for ticker in selected_tickers:
        data = data_loader(
            ticker,
            fetch_start.isoformat(),
            fetch_end.isoformat(),
            "15m",
        )
        if data is None:
            continue

        loaded_data[ticker] = data
        analysis = _historical_analysis(ticker, data, parsed_date)
        if analysis is not None:
            analyses.append(analysis)

    analyses.sort(key=lambda result: result["momentum_score"], reverse=True)
    trades = [
        _next_trading_day_result(analysis, loaded_data[analysis["ticker"]])
        for analysis in analyses[:5]
    ]
    evaluated_trades = [
        trade for trade in trades
        if trade["status"] in {"successful", "failed"}
    ]
    successful_trades = sum(
        trade["status"] == "successful"
        for trade in evaluated_trades
    )

    result = {
        "analysis_date": parsed_date.isoformat(),
        "data_interval": "15m",
        "entry_rule": "first 15-minute bar on next trading day touches mean of planned buy zone",
        "exit_rule": "later 15-minute bar touches min(mean of planned sell target, 0.5% above planned entry)",
        "success_rule": "entry and exit levels are reached in chronological order on the next trading day",
        "stocks_selected": len(trades),
        "trades_evaluated": len(evaluated_trades),
        "successful_trades": successful_trades,
        "failed_trades": sum(
            trade["status"] == "failed"
            for trade in evaluated_trades
        ),
        "neutral_trades": sum(
            trade["status"] == "neutral" for trade in trades
        ),
        "unavailable_trades": sum(
            trade["status"] == "next_trading_day_unavailable"
            for trade in trades
        ),
        "trades": trades,
    }

    destination = Path(output_path or (
        Path("backtest_results")
        / f"backtest_{parsed_date.isoformat()}.json"
    ))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    result["output_path"] = str(destination)
    return result


def run_backtest_range(
    start_date: str,
    end_date: str,
    output_dir: str | Path | None = None,
    tickers: list[str] | None = None,
    data_loader: DataLoader = get_stock_history_between,
) -> dict:
    """Run one backtest for every calendar date in an inclusive date range.

    Each date gets its own JSON result, and a consolidated JSON file contains
    all daily results plus aggregate trade counts. Dates without enough market
    data produce a valid daily result with zero selected stocks.
    """

    first_date = _parse_analysis_date(start_date)
    last_date = _parse_analysis_date(end_date)
    if first_date > last_date:
        raise ValueError("start_date must not be after end_date")

    destination_dir = Path(output_dir or "backtest_results")
    destination_dir.mkdir(parents=True, exist_ok=True)
    daily_results = []
    current_date = first_date

    while current_date <= last_date:
        date_text = current_date.isoformat()
        daily_results.append(
            run_backtest(
                date_text,
                output_path=destination_dir / f"backtest_{date_text}.json",
                tickers=tickers,
                data_loader=data_loader,
            )
        )
        current_date += timedelta(days=1)

    trades_evaluated = sum(
        result["trades_evaluated"] for result in daily_results
    )
    successful_trades = sum(
        result["successful_trades"] for result in daily_results
    )
    consolidated = {
        "start_date": first_date.isoformat(),
        "end_date": last_date.isoformat(),
        "dates_processed": len(daily_results),
        "stocks_selected": sum(
            result["stocks_selected"] for result in daily_results
        ),
        "trades_evaluated": trades_evaluated,
        "successful_trades": successful_trades,
        "failed_trades": sum(
            result["failed_trades"] for result in daily_results
        ),
        "neutral_trades": sum(
            result["neutral_trades"] for result in daily_results
        ),
        "unavailable_trades": sum(
            result["unavailable_trades"] for result in daily_results
        ),
        "success_rate_pct": round(
            successful_trades / trades_evaluated * 100,
            2,
        ) if trades_evaluated else None,
        "daily_results": daily_results,
    }
    consolidated_path = destination_dir / (
        f"backtest_{first_date.isoformat()}_to_{last_date.isoformat()}.json"
    )
    consolidated_path.write_text(json.dumps(consolidated, indent=2) + "\n")
    consolidated["output_path"] = str(consolidated_path)
    return consolidated


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backtest the top five momentum stocks for one or more dates."
    )
    parser.add_argument("start_date", help="Analysis date in YYYY-MM-DD format")
    parser.add_argument(
        "end_date",
        nargs="?",
        help="Optional inclusive end date in YYYY-MM-DD format",
    )
    parser.add_argument("--output", dest="output_path")
    parser.add_argument("--output-dir", dest="output_dir")
    args = parser.parse_args()
    if args.end_date:
        print(json.dumps(
            run_backtest_range(
                args.start_date,
                args.end_date,
                args.output_dir,
            ),
            indent=2,
        ))
    else:
        print(json.dumps(run_backtest(args.start_date, args.output_path), indent=2))