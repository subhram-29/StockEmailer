from typing import Optional

import pandas as pd

from stockemailer.data.market_data import get_stock_history
from stockemailer.analysis.indicators import calculate_extended_indicators
from stockemailer.analysis.patterns import detect_patterns
from stockemailer.analysis.price_targets import calculate_price_range


def _rounded_or_none(value: object, decimals: int) -> float | None:
    """Return a rounded number, or None when the value is unavailable."""

    if pd.isna(value):
        return None

    return round(float(value), decimals)


EXTENDED_SCORE_COLUMNS = (
    "ATR_14", "BOLL_UPPER", "BOLL_MIDDLE", "BOLL_LOWER", "BOLL_WIDTH",
    "ADX_14", "PLUS_DI", "MINUS_DI", "STOCH_K", "STOCH_D", "CCI_20",
    "WILLIAMS_R", "OBV", "OBV_SLOPE_5", "VWAP_20", "ROC_10",
    "BULLISH_ENGULFING", "BEARISH_ENGULFING", "HAMMER", "SHOOTING_STAR",
    "DOJI", "THREE_WHITE_SOLDIERS", "GOLDEN_CROSS", "DEATH_CROSS",
)


def calculate_momentum_score(row: pd.Series) -> float:
    """
    Calculate a deterministic momentum score using all available signals.

    Legacy signals contribute up to 9 points and retained extended
    confirmation signals contribute up to 8 additional points before
    bearish-pattern deductions.
    """

    score = 0.0

    # 2-day return
    return_2d = row["RETURN_2D"]

    if return_2d >= 5:
        score += 3
    elif return_2d >= 3:
        score += 2
    elif return_2d >= 1:
        score += 1

    # Volume confirmation
    volume_ratio = row["VOLUME_RATIO"]

    if volume_ratio >= 2:
        score += 2
    elif volume_ratio >= 1.5:
        score += 1.5
    elif volume_ratio >= 1.2:
        score += 1

    # RSI
    rsi = row["RSI"]

    if 55 <= rsi <= 70:
        score += 1

    # Moving-average trend
    if (
        row["Close"] > row["SMA_20"]
        and row["SMA_20"] > row["SMA_50"]
    ):
        score += 1

    # MACD
    if row["MACD"] > row["MACD_SIGNAL"]:
        score += 1

    # 5-day momentum
    if row["RETURN_5D"] > 0:
        score += 1

    extended_columns = {
        "ATR_14",
        "BOLL_UPPER",
        "BOLL_MIDDLE",
        "BOLL_LOWER",
        "BOLL_WIDTH",
        "ADX_14",
        "PLUS_DI",
        "MINUS_DI",
        "STOCH_K",
        "STOCH_D",
        "CCI_20",
        "WILLIAMS_R",
        "OBV",
        "OBV_SLOPE_5",
        "VWAP_20",
        "ROC_10",
        "BULLISH_ENGULFING",
        "BEARISH_ENGULFING",
        "HAMMER",
        "SHOOTING_STAR",
        "DOJI",
        "THREE_WHITE_SOLDIERS",
        "GOLDEN_CROSS",
        "DEATH_CROSS",
    }
    if not extended_columns.issubset(row.index):
        return round(score, 2)

    # Extended volatility and trend confirmation.
    extended_score = 0.0

    if row["ATR_14"] / row["Close"] <= 0.03:
        extended_score += 0.5
    if row["BOLL_WIDTH"] <= 10:
        extended_score += 0.5
    if row["Close"] > row["BOLL_MIDDLE"]:
        extended_score += 0.5
    if row["Close"] > row["BOLL_LOWER"]:
        extended_score += 0.5
    if row["Close"] < row["BOLL_UPPER"]:
        extended_score += 0.5
    if row["ADX_14"] >= 20:
        extended_score += 0.5
    # Extended oscillator and volume confirmation. RSI remains the representative
    # oscillator in the legacy score; correlated CCI, Williams %R, ROC, and DI
    # signals remain available for reporting but do not add duplicate points.
    if row["STOCH_K"] > row["STOCH_D"]:
        extended_score += 0.5
    if row["OBV"] > 0:
        extended_score += 0.5
    if row["OBV_SLOPE_5"] > 0:
        extended_score += 0.5
    if row["Close"] > row["VWAP_20"]:
        extended_score += 0.5

    # Bullish patterns add confirmation; bearish patterns subtract it.
    for pattern_name in (
        "BULLISH_ENGULFING",
        "HAMMER",
        "THREE_WHITE_SOLDIERS",
        "GOLDEN_CROSS",
    ):
        if row[pattern_name]:
            extended_score += 0.75

    for pattern_name in (
        "BEARISH_ENGULFING",
        "SHOOTING_STAR",
        "DEATH_CROSS",
    ):
        if row[pattern_name]:
            extended_score -= 0.5

    if row["DOJI"]:
        extended_score -= 0.25

    return round(score + extended_score, 2)


def calculate_score_components(row: pd.Series) -> dict[str, float]:
    """Return the individual deterministic contributions to the score."""

    components = {
        "return_2d": 0.0,
        "volume": 0.0,
        "rsi": 0.0,
        "moving_average_alignment": 0.0,
        "macd": 0.0,
        "return_5d": 0.0,
    }
    if row["RETURN_2D"] >= 5:
        components["return_2d"] = 3.0
    elif row["RETURN_2D"] >= 3:
        components["return_2d"] = 2.0
    elif row["RETURN_2D"] >= 1:
        components["return_2d"] = 1.0
    if row["VOLUME_RATIO"] >= 2:
        components["volume"] = 2.0
    elif row["VOLUME_RATIO"] >= 1.5:
        components["volume"] = 1.5
    elif row["VOLUME_RATIO"] >= 1.2:
        components["volume"] = 1.0
    if 55 <= row["RSI"] <= 70:
        components["rsi"] = 1.0
    if row["Close"] > row["SMA_20"] > row["SMA_50"]:
        components["moving_average_alignment"] = 1.0
    if row["MACD"] > row["MACD_SIGNAL"]:
        components["macd"] = 1.0
    if row["RETURN_5D"] > 0:
        components["return_5d"] = 1.0

    if not set(EXTENDED_SCORE_COLUMNS).issubset(row.index):
        return components

    components.update({
        "atr_low_relative_to_close": 0.5 if row["ATR_14"] / row["Close"] <= 0.03 else 0.0,
        "bollinger_width": 0.5 if row["BOLL_WIDTH"] <= 10 else 0.0,
        "above_bollinger_middle": 0.5 if row["Close"] > row["BOLL_MIDDLE"] else 0.0,
        "above_bollinger_lower": 0.5 if row["Close"] > row["BOLL_LOWER"] else 0.0,
        "below_bollinger_upper": 0.5 if row["Close"] < row["BOLL_UPPER"] else 0.0,
        "adx": 0.5 if row["ADX_14"] >= 20 else 0.0,
        "stochastic": 0.5 if row["STOCH_K"] > row["STOCH_D"] else 0.0,
        "obv_positive": 0.5 if row["OBV"] > 0 else 0.0,
        "obv_slope": 0.5 if row["OBV_SLOPE_5"] > 0 else 0.0,
        "above_vwap": 0.5 if row["Close"] > row["VWAP_20"] else 0.0,
    })
    for pattern_name in ("BULLISH_ENGULFING", "HAMMER", "THREE_WHITE_SOLDIERS", "GOLDEN_CROSS"):
        components[pattern_name.lower()] = 0.75 if row[pattern_name] else 0.0
    for pattern_name in ("BEARISH_ENGULFING", "SHOOTING_STAR", "DEATH_CROSS"):
        components[pattern_name.lower()] = -0.5 if row[pattern_name] else 0.0
    components["doji"] = -0.25 if row["DOJI"] else 0.0
    return components


def analyze_stock(ticker: str) -> Optional[dict]:
    """
    Download data and calculate all signals for one stock.
    """

    data = get_stock_history(ticker)

    if data is None or len(data) < 50:
        return None

    data = calculate_extended_indicators(data)
    data = detect_patterns(data)

    latest = data.iloc[-1]

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

    score = calculate_momentum_score(latest)

    try:
        price_range = calculate_price_range(data)
    except ValueError:
        price_range = None

    return {
        "ticker": ticker,
        "date": data.index[-1].strftime("%Y-%m-%d"),
        "close": round(float(latest["Close"]), 2),
        "return_1d": round(float(latest["RETURN_1D"]), 2),
        "return_2d": round(float(latest["RETURN_2D"]), 2),
        "return_5d": round(float(latest["RETURN_5D"]), 2),
        "volume_ratio": round(float(latest["VOLUME_RATIO"]), 2),
        "rsi": round(float(latest["RSI"]), 2),
        "sma_20": round(float(latest["SMA_20"]), 2),
        "sma_50": round(float(latest["SMA_50"]), 2),
        "macd": round(float(latest["MACD"]), 4),
        "macd_signal": round(float(latest["MACD_SIGNAL"]), 4),
        "above_20dma": bool(latest["Close"] > latest["SMA_20"]),
        "above_50dma": bool(latest["Close"] > latest["SMA_50"]),
        "macd_bullish": bool(
            latest["MACD"] > latest["MACD_SIGNAL"]
        ),
        "atr_14": _rounded_or_none(latest["ATR_14"], 4),
        "boll_upper": _rounded_or_none(latest["BOLL_UPPER"], 2),
        "boll_middle": _rounded_or_none(latest["BOLL_MIDDLE"], 2),
        "boll_lower": _rounded_or_none(latest["BOLL_LOWER"], 2),
        "boll_width": _rounded_or_none(latest["BOLL_WIDTH"], 2),
        "adx_14": _rounded_or_none(latest["ADX_14"], 2),
        "plus_di": _rounded_or_none(latest["PLUS_DI"], 2),
        "minus_di": _rounded_or_none(latest["MINUS_DI"], 2),
        "stoch_k": _rounded_or_none(latest["STOCH_K"], 2),
        "stoch_d": _rounded_or_none(latest["STOCH_D"], 2),
        "cci_20": _rounded_or_none(latest["CCI_20"], 2),
        "williams_r": _rounded_or_none(latest["WILLIAMS_R"], 2),
        "obv": _rounded_or_none(latest["OBV"], 2),
        "obv_slope_5": _rounded_or_none(latest["OBV_SLOPE_5"], 6),
        "vwap_20": _rounded_or_none(latest["VWAP_20"], 2),
        "roc_10": _rounded_or_none(latest["ROC_10"], 2),
        "bullish_engulfing": bool(latest["BULLISH_ENGULFING"]),
        "bearish_engulfing": bool(latest["BEARISH_ENGULFING"]),
        "hammer": bool(latest["HAMMER"]),
        "shooting_star": bool(latest["SHOOTING_STAR"]),
        "doji": bool(latest["DOJI"]),
        "three_white_soldiers": bool(latest["THREE_WHITE_SOLDIERS"]),
        "golden_cross": bool(latest["GOLDEN_CROSS"]),
        "death_cross": bool(latest["DEATH_CROSS"]),
        "momentum_score": score,
        "price_range": price_range,
    }

from stockemailer.data.universe import NSE_STOCKS


def screen_market(
    tickers: list[str] | None = None,
    top_n: int = 20,
) -> list[dict]:

    if tickers is None:
        tickers = NSE_STOCKS

    results = []

    print(f"Scanning {len(tickers)} stocks...")

    for ticker in tickers:

        print(f"Analyzing {ticker}...")

        result = analyze_stock(ticker)

        if result is not None:
            results.append(result)

    results.sort(
        key=lambda x: x["momentum_score"],
        reverse=True,
    )

    return results[:top_n]