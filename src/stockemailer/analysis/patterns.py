import pandas as pd


def bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    """Return rows where a bullish candle engulfs the prior bearish candle."""

    previous_open = df["Open"].shift(1)
    previous_close = df["Close"].shift(1)
    return (
        (previous_close < previous_open)
        & (df["Close"] > df["Open"])
        & (df["Open"] <= previous_close)
        & (df["Close"] >= previous_open)
    ).fillna(False)


def bearish_engulfing(df: pd.DataFrame) -> pd.Series:
    """Return rows where a bearish candle engulfs the prior bullish candle."""

    previous_open = df["Open"].shift(1)
    previous_close = df["Close"].shift(1)
    return (
        (previous_close > previous_open)
        & (df["Close"] < df["Open"])
        & (df["Open"] >= previous_close)
        & (df["Close"] <= previous_open)
    ).fillna(False)


def hammer(df: pd.DataFrame) -> pd.Series:
    """Return rows with a small body, long lower wick, and short upper wick."""

    body = (df["Close"] - df["Open"]).abs()
    candle_range = df["High"] - df["Low"]
    lower_wick = df[["Open", "Close"]].min(axis=1) - df["Low"]
    upper_wick = df["High"] - df[["Open", "Close"]].max(axis=1)
    return (
        (candle_range > 0)
        & (lower_wick >= 2 * body)
        & (upper_wick <= body)
    ).fillna(False)


def shooting_star(df: pd.DataFrame) -> pd.Series:
    """Return rows with a small body, long upper wick, and short lower wick."""

    body = (df["Close"] - df["Open"]).abs()
    candle_range = df["High"] - df["Low"]
    lower_wick = df[["Open", "Close"]].min(axis=1) - df["Low"]
    upper_wick = df["High"] - df[["Open", "Close"]].max(axis=1)
    return (
        (candle_range > 0)
        & (upper_wick >= 2 * body)
        & (lower_wick <= body)
    ).fillna(False)


def doji(df: pd.DataFrame) -> pd.Series:
    """Return rows whose open-close body is below ten percent of the range."""

    body = (df["Close"] - df["Open"]).abs()
    candle_range = df["High"] - df["Low"]
    return (
        (candle_range > 0)
        & (body < 0.1 * candle_range)
    ).fillna(False)


def three_white_soldiers(df: pd.DataFrame) -> pd.Series:
    """Return rows ending three bullish candles with higher closes and small lower wicks."""

    body = (df["Close"] - df["Open"]).abs()
    lower_wick = df[["Open", "Close"]].min(axis=1) - df["Low"]
    bullish = df["Close"] > df["Open"]
    higher_closes = df["Close"].gt(df["Close"].shift(1))
    small_lower_wicks = lower_wick <= body
    return (
        bullish
        & bullish.shift(1)
        & bullish.shift(2)
        & higher_closes
        & higher_closes.shift(1)
        & higher_closes.shift(2)
        & small_lower_wicks
        & small_lower_wicks.shift(1)
        & small_lower_wicks.shift(2)
    ).fillna(False)


def golden_cross(df: pd.DataFrame) -> pd.Series:
    """Return rows where SMA-50 crosses above SMA-200."""

    sma_50 = df["Close"].rolling(50).mean()
    sma_200 = df["Close"].rolling(200).mean()
    return (
        (sma_50 > sma_200)
        & (sma_50.shift(1) <= sma_200.shift(1))
    ).fillna(False)


def death_cross(df: pd.DataFrame) -> pd.Series:
    """Return rows where SMA-50 crosses below SMA-200."""

    sma_50 = df["Close"].rolling(50).mean()
    sma_200 = df["Close"].rolling(200).mean()
    return (
        (sma_50 < sma_200)
        & (sma_50.shift(1) >= sma_200.shift(1))
    ).fillna(False)


def detect_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of OHLC data with candlestick and price-action flags."""

    result = df.copy()
    result["BULLISH_ENGULFING"] = bullish_engulfing(result)
    result["BEARISH_ENGULFING"] = bearish_engulfing(result)
    result["HAMMER"] = hammer(result)
    result["SHOOTING_STAR"] = shooting_star(result)
    result["DOJI"] = doji(result)
    result["THREE_WHITE_SOLDIERS"] = three_white_soldiers(result)
    result["GOLDEN_CROSS"] = golden_cross(result)
    result["DEATH_CROSS"] = death_cross(result)
    return result