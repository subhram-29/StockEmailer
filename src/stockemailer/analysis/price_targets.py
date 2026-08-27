import math

import pandas as pd
from scipy.stats import norm


def calculate_price_range(
    df: pd.DataFrame,
    horizon_days: int = 5,
    confidence: float = 0.90,
) -> dict:
    """Project an indicative price range from historical daily volatility.

    This is a statistical projection from historical volatility under a
    normal-distribution assumption, not a prediction or guarantee. Real
    markets are not normally distributed and have fat tails, so treat this
    range as indicative rather than precise. The buy zone is a modest
    pullback from the latest close, while the sell target extends to the
    upper projected range at the requested confidence level.
    """

    if horizon_days <= 0:
        raise ValueError("horizon_days must be greater than zero")

    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    if "Close" not in df.columns:
        raise ValueError("Close column is required to calculate a price range")

    close = pd.to_numeric(df["Close"], errors="coerce")
    close = close[close.notna() & close.notna().map(math.isfinite)]

    if len(close) < 10:
        raise ValueError(
            "At least 10 valid Close values are required to calculate a price range"
        )

    if (close <= 0).any():
        raise ValueError("Close values must be positive to calculate log returns")

    log_returns = (close / close.shift(1)).apply(math.log).dropna()
    recent_log_returns = log_returns.tail(20)
    sigma_daily = recent_log_returns.std()
    last_close = float(close.iloc[-1])

    if pd.isna(sigma_daily):
        raise ValueError("Unable to calculate volatility from Close values")

    sigma_horizon = float(sigma_daily) * math.sqrt(horizon_days)
    z_score = float(norm.ppf((1 + confidence) / 2))

    buy_zone_low = last_close * math.exp(-0.5 * z_score * sigma_horizon)
    sell_target_high = last_close * math.exp(z_score * sigma_horizon)

    return {
        "last_close": round(last_close, 2),
        "buy_zone_low": round(buy_zone_low, 2),
        "buy_zone_high": round(last_close, 2),
        "sell_target_low": round(last_close, 2),
        "sell_target_high": round(sell_target_high, 2),
        "horizon_days": horizon_days,
        "confidence": confidence,
        "sigma_daily_pct": round(float(sigma_daily) * 100, 2),
        "method": "historical_volatility_normal_approx",
    }
