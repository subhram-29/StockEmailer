import json
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from stockemailer.analysis.indicators import calculate_extended_indicators
from stockemailer.analysis.patterns import detect_patterns
from stockemailer.data.market_data import get_stock_history
from stockemailer.data.universe import NSE_STOCKS


DataLoader = Callable[[str, str, str], pd.DataFrame | None]
DEFAULT_FORWARD_HORIZONS = (1, 5, 10)
DEFAULT_CORRELATION_THRESHOLD = 0.80

INDICATOR_COLUMNS = (
    "RETURN_1D",
    "RETURN_2D",
    "RETURN_5D",
    "VOLUME_RATIO",
    "RSI",
    "SMA_20",
    "SMA_50",
    "SMA_200",
    "MACD",
    "MACD_SIGNAL",
    "MACD_HIST",
    "ATR_14",
    "BOLL_WIDTH",
    "ADX_14",
    "PLUS_DI",
    "MINUS_DI",
    "STOCH_K",
    "STOCH_D",
    "CCI_20",
    "WILLIAMS_R",
    "OBV_SLOPE_5",
    "VWAP_20",
    "ROC_10",
)

PATTERN_COLUMNS = (
    "BULLISH_ENGULFING",
    "BEARISH_ENGULFING",
    "HAMMER",
    "SHOOTING_STAR",
    "DOJI",
    "THREE_WHITE_SOLDIERS",
    "GOLDEN_CROSS",
    "DEATH_CROSS",
)


def _spearman_correlation(left: pd.Series, right: pd.Series) -> float | None:
    """Calculate Spearman correlation, returning None for insufficient data."""

    values = pd.concat([left, right], axis=1).dropna()
    if len(values) < 3 or values.iloc[:, 0].nunique() < 2:
        return None

    return float(values.iloc[:, 0].rank().corr(values.iloc[:, 1].rank()))


def _analysis_features(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate features used by the score without mutating source data."""

    enriched = detect_patterns(calculate_extended_indicators(data))
    features = enriched.copy()
    features["ATR_PCT"] = features["ATR_14"] / features["Close"] * 100
    features["CLOSE_ABOVE_BOLL_MIDDLE"] = (
        features["Close"] > features["BOLL_MIDDLE"]
    ).astype(float)
    features["CLOSE_ABOVE_VWAP"] = (
        features["Close"] > features["VWAP_20"]
    ).astype(float)
    features["MA_TREND_ALIGNMENT"] = (
        (features["Close"] > features["SMA_20"])
        & (features["SMA_20"] > features["SMA_50"])
    ).astype(float)
    features["MACD_BULLISH"] = (
        features["MACD"] > features["MACD_SIGNAL"]
    ).astype(float)
    features["STOCH_SPREAD"] = features["STOCH_K"] - features["STOCH_D"]
    return features


def build_validation_frame(
    market_data: Iterable[tuple[str, pd.DataFrame]],
    forward_horizons: tuple[int, ...] = DEFAULT_FORWARD_HORIZONS,
) -> pd.DataFrame:
    """Build a pooled feature/forward-return frame for multiple tickers."""

    frames = []
    for ticker, data in market_data:
        features = _analysis_features(data)
        for horizon in forward_horizons:
            features[f"FORWARD_RETURN_{horizon}D"] = (
                data["Close"].shift(-horizon) / data["Close"] - 1
            ) * 100
        features["TICKER"] = ticker
        frames.append(features)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, axis=0)


def calculate_information_coefficients(
    validation_frame: pd.DataFrame,
    forward_horizons: tuple[int, ...] = DEFAULT_FORWARD_HORIZONS,
) -> dict:
    """Calculate pooled Spearman ICs between features and forward returns.

    An IC is the rank correlation between a feature observed on day T and the
    future return over the requested horizon. Positive values indicate that
    larger feature values tended to precede larger returns in this dataset;
    values near zero indicate little monotonic predictive relationship.
    """

    result = {}
    for feature in INDICATOR_COLUMNS + PATTERN_COLUMNS + (
        "ATR_PCT",
        "CLOSE_ABOVE_BOLL_MIDDLE",
        "CLOSE_ABOVE_VWAP",
        "MA_TREND_ALIGNMENT",
        "MACD_BULLISH",
        "STOCH_SPREAD",
    ):
        result[feature] = {}
        for horizon in forward_horizons:
            target = f"FORWARD_RETURN_{horizon}D"
            values = validation_frame[[feature, target]].dropna()
            result[feature][str(horizon)] = {
                "ic": _spearman_correlation(values[feature], values[target]),
                "observations": len(values),
            }

    return result


def calculate_multicollinearity(
    validation_frame: pd.DataFrame,
    correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD,
) -> dict:
    """Report feature correlations, highly correlated pairs, and VIF values."""

    feature_columns = [
        "RETURN_2D",
        "VOLUME_RATIO",
        "RSI",
        "MA_TREND_ALIGNMENT",
        "MACD_BULLISH",
        "RETURN_5D",
        "ATR_PCT",
        "BOLL_WIDTH",
        "ADX_14",
        "PLUS_DI",
        "MINUS_DI",
        "STOCH_SPREAD",
        "CCI_20",
        "WILLIAMS_R",
        "OBV_SLOPE_5",
        "CLOSE_ABOVE_VWAP",
        "ROC_10",
    ]
    available = [column for column in feature_columns if column in validation_frame]
    numeric = validation_frame[available].apply(pd.to_numeric, errors="coerce")
    correlation = numeric.corr(method="spearman")
    high_pairs = []
    for index, left in enumerate(available):
        for right in available[index + 1:]:
            value = correlation.loc[left, right]
            if pd.notna(value) and abs(value) >= correlation_threshold:
                high_pairs.append({
                    "feature_a": left,
                    "feature_b": right,
                    "spearman_correlation": round(float(value), 4),
                })

    complete = numeric.dropna()
    vif = {feature: None for feature in available}
    varying = [
        feature for feature in available
        if complete[feature].nunique() > 1
    ]
    if len(complete) >= len(varying) + 2 and varying:
        matrix = complete[varying].to_numpy(dtype=float)
        matrix = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0)
        inverse_correlation = np.linalg.pinv(
            np.corrcoef(matrix, rowvar=False)
        )
        for index, feature in enumerate(varying):
            value = inverse_correlation[index, index]
            vif[feature] = (
                None if not np.isfinite(value) else round(float(value), 4)
            )

    return {
        "features": available,
        "spearman_correlation": correlation.round(4).where(
            correlation.notna(), None
        ).to_dict(),
        "high_correlation_pairs": high_pairs,
        "vif": vif,
    }


def run_signal_validation(
    tickers: list[str] | None = None,
    period: str = "2y",
    forward_horizons: tuple[int, ...] = DEFAULT_FORWARD_HORIZONS,
    output_path: str | Path | None = None,
    data_loader: DataLoader = get_stock_history,
) -> dict:
    """Download history and write IC/multicollinearity diagnostics as JSON."""

    selected_tickers = tickers if tickers is not None else NSE_STOCKS
    loaded_data = []
    failed_tickers = []
    for ticker in selected_tickers:
        data = data_loader(ticker, period, "1d")
        if data is None:
            failed_tickers.append(ticker)
            continue
        loaded_data.append((ticker, data))

    validation_frame = build_validation_frame(loaded_data, forward_horizons)
    result = {
        "period": period,
        "tickers_requested": len(selected_tickers),
        "tickers_loaded": len(loaded_data),
        "failed_tickers": failed_tickers,
        "forward_horizons_days": list(forward_horizons),
        "observations": len(validation_frame),
        "information_coefficients": calculate_information_coefficients(
            validation_frame,
            forward_horizons,
        ),
        "multicollinearity": calculate_multicollinearity(validation_frame),
    }
    destination = Path(output_path or "signal_validation.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    result["output_path"] = str(destination)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Measure signal IC and multicollinearity."
    )
    parser.add_argument("--period", default="2y")
    parser.add_argument("--output", default="signal_validation.json")
    args = parser.parse_args()
    print(json.dumps(run_signal_validation(period=args.period, output_path=args.output), indent=2))
