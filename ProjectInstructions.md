# StockEmailer Project Instructions

## Purpose

StockEmailer is a Python application intended to produce a daily Indian stock momentum research report. It scans a fixed set of NSE-listed symbols using historical Yahoo Finance data, calculates deterministic technical indicators and a momentum score, asks a Gemini model to select and explain the five strongest candidates, and sends the resulting plain-text report through Gmail.

The project is a research/reporting tool. It is not a trading system, portfolio manager, broker integration, order-entry system, or personalized financial-advice system. It must not promise returns or imply that a screened stock is guaranteed to rise.

The intended processing pipeline is:

```text
environment/configuration
        -> Yahoo Finance historical OHLCV data
        -> technical indicators
        -> deterministic momentum scoring
        -> top-20 market screen
        -> Gemini selection and explanation of five stocks
        -> Gmail OAuth/API plain-text delivery
```

## Current Repository State

This document describes the code as it exists today. It should be updated when behavior, dependencies, credentials, or operational workflows change.

- Package name: `stockemailer`
- Version: `0.1.0`
- Python requirement: `>=3.14`
- Preferred Python version file: `.python-version` contains `3.14`
- Build backend: `uv_build>=0.12.5,<0.13.0`
- Dependency lockfile: `uv.lock`
- Source layout: `src/stockemailer`
- README: currently empty
- Automated tests: none currently configured
- CI configuration: none currently present
- Logging: uses `print`; no structured logging exists
- Persistent application storage: none, apart from the Gmail OAuth token

The root currently also expects local runtime files named `.env`, `credentials.json`, and `token.json`. These files are ignored by Git and must never be copied into source control or included in generated documentation.

## Repository Layout

```text
StockEmailer/
|-- .gitignore
|-- .python-version
|-- ProjectInstructions.md
|-- README.md
|-- credentials.json       # local Google OAuth client secret; ignored
|-- token.json             # local Gmail OAuth token; ignored
|-- pyproject.toml
|-- uv.lock
|-- src/
    |-- stockemailer/
        |-- __init__.py
        |-- backtesting.py
        |-- config.py
        |-- main.py
        |-- agent/
        |   |-- __init__.py
        |   `-- gemini_agent.py
        |-- analysis/
        |   |-- __init__.py
        |   |-- indicators.py
        |   `-- screener.py
        |-- data/
        |   |-- __init__.py
        |   |-- market_data.py
        |   `-- universe.py
        `-- notifications/
            |-- gmail.py
            `-- test_email.py
```

The package initializers are empty except for the root package's placeholder `main()` function. There are no classes in the application; behavior is organized as module-level functions and constants.

The empty package initializer files are `src/stockemailer/agent/__init__.py`, `src/stockemailer/analysis/__init__.py`, and `src/stockemailer/data/__init__.py`. The root initializer, `src/stockemailer/__init__.py`, is the exception: it defines the placeholder package-level `main() -> None` that prints `Hello from stockemailer!`. The notifications directory currently has no `__init__.py` file.

## Setup and Dependencies

The project uses `uv` and the `src` package layout. From the repository root:

```bash
uv sync
```

The declared direct dependencies are:

- `google-api-python-client`: Gmail API client
- `google-auth-httplib2`: Google API HTTP authentication support
- `google-auth-oauthlib`: installed-app OAuth flow
- `google-genai`: Gemini API client and function/tool schemas
- `numpy`: numerical dependency of the data/indicator stack
- `pandas`: tabular market data and indicator frames
- `python-dotenv`: loads `.env` values into the process environment
- `ta`: technical-analysis indicator implementations
- `scipy`: normal-distribution quantiles for deterministic price-range projections
- `yfinance`: Yahoo Finance historical data download

`pyproject.toml` declares lower bounds, while `uv.lock` records the resolved environment. Keep the lockfile synchronized with dependency changes. Do not casually upgrade the Python requirement or dependency major versions without checking compatibility with Python 3.14, `pandas`, `yfinance`, `ta`, Google APIs, and `google-genai`.

## Required Runtime Configuration

Create a local `.env` file at the repository root. The current code requires:

```dotenv
GEMINI_API_KEY=replace-with-a-gemini-api-key
EMAIL_RECIPIENT=recipient@example.com
```

### `GEMINI_API_KEY`

- Read by `stockemailer.config` using `os.getenv` after `load_dotenv()`.
- Required during import, not merely when the analysis function runs.
- Missing value raises `ValueError` with a configuration message.
- Never print, commit, persist in source, or place the value in this document.

### `EMAIL_RECIPIENT`

- Read by `stockemailer.main.main()` immediately before email delivery.
- Also read by `stockemailer.notifications.test_email`.
- Missing value raises `ValueError`.
- The current implementation treats it as one recipient string. No recipient-list parsing or validation is implemented.

### Google OAuth files

Gmail delivery expects these files at the repository root:

- `credentials.json`: Google OAuth client-secrets file supplied by a Google Cloud project.
- `token.json`: generated authorized-user credentials and refresh token.

The Gmail scope is exactly `https://www.googleapis.com/auth/gmail.send`. On the first run, the installed-app flow opens a browser and starts a local callback server. Later runs use the saved token and refresh it when necessary. Do not inspect, log, or document the contents of either file. Protect them with filesystem permissions appropriate for secrets.

## Entry Points and Execution

### Intended application run

The real executable flow is in `stockemailer.main`:

```bash
uv run python -m stockemailer.main
```

This flow prints a banner, calls `analyze_market()`, prints the generated report, checks `EMAIL_RECIPIENT`, sends the report with subject `Daily Indian Stock Momentum Report`, and prints a success message.

### Console command

`pyproject.toml` declares:

```toml
[project.scripts]
stockemailer = "stockemailer.main:main"
```

Run the installed application with:

```bash
uv run stockemailer
```

This invokes the real `stockemailer.main:main` workflow. The package-level `stockemailer/__init__.py` function remains a placeholder and should not be used as the application entry point.

### Email smoke test (`src/stockemailer/notifications/test_email.py`)

The file `stockemailer.notifications.test_email` is not an automated test. It executes at import/module-run time and sends an actual Gmail message with subject `Stock Agent - Gmail Test`.

Run it only when a real email is intentionally desired:

```bash
uv run python -m stockemailer.notifications.test_email
```

Do not import this module from unit tests. A future change should move its behavior behind an explicit `main()` guard or replace it with non-delivery tests.

## Module Responsibilities

### `stockemailer.config` (`src/stockemailer/config.py`)

Loads dotenv values and defines:

- `GEMINI_API_KEY`: required API key
- `GEMINI_MODEL`: currently `gemini-3-flash-preview`

This module has import-time validation. New configuration should preferably be centralized here, validated clearly, and avoid leaking secrets in exception messages or logs.

### `stockemailer.data.universe` (`src/stockemailer/data/universe.py`)

Defines `NSE_STOCKS`, the default hard-coded universe of Yahoo Finance NSE symbols:

```text
RELIANCE.NS, TCS.NS, HDFCBANK.NS, ICICIBANK.NS, INFY.NS,
ITC.NS, SBIN.NS, BHARTIARTL.NS, LT.NS, AXISBANK.NS,
KOTAKBANK.NS, HINDUNILVR.NS, MARUTI.NS, SUNPHARMA.NS,
M&M.NS, ADANIENT.NS, ADANIPORTS.NS, TITAN.NS, BAJFINANCE.NS,
BAJAJFINSV.NS, HCLTECH.NS, WIPRO.NS, TECHM.NS, NTPC.NS,
POWERGRID.NS, ONGC.NS, COALINDIA.NS, TATASTEEL.NS, JSWSTEEL.NS
```

`TATAMOTORS.NS` is present only as a commented-out candidate and is not scanned. The list is ordered but ranking is later determined by score. There is no external universe file, exchange-membership refresh, sector balancing, deduplication, or configuration override.

### `stockemailer.data.market_data` (`src/stockemailer/data/market_data.py`)

`get_stock_history(ticker, period="6mo", interval="1d") -> Optional[pandas.DataFrame]` calls:

```python
yf.download(
    ticker,
    period=period,
    interval=interval,
    auto_adjust=True,
    progress=False,
)
```

Behavior:

1. Returns `None` when Yahoo Finance returns an empty frame.
2. Flattens a `pandas.MultiIndex` column index by taking level zero.
3. Drops rows containing missing values with `dropna()`.
4. Catches every exception, prints an error, and returns `None`.

Downstream code expects at least `Close` and `Volume` columns. There is no explicit schema validation, retry, timeout, caching, rate-limit handling, stale-data detection, trading-calendar handling, or provider abstraction. Preserve Yahoo-specific behavior in this module when adding another data source.

### `stockemailer.analysis.indicators` (`src/stockemailer/analysis/indicators.py`)

`calculate_indicators(df) -> pandas.DataFrame` copies the input and adds technical columns using `ta`:

- `SMA_20`: 20-period simple moving average of `Close`
- `SMA_50`: 50-period simple moving average of `Close`
- `SMA_200`: 200-period simple moving average of `Close`
- `RSI`: 14-period relative strength index of `Close`
- `MACD`: default `ta.trend.MACD` MACD line
- `MACD_SIGNAL`: default MACD signal line
- `MACD_HIST`: default MACD difference/histogram
- `RETURN_1D`: one-period percentage return, multiplied by 100
- `RETURN_2D`: two-period percentage return, multiplied by 100
- `RETURN_5D`: five-period percentage return, multiplied by 100
- `AVG_VOLUME_20`: 20-period rolling mean of `Volume`
- `VOLUME_RATIO`: `Volume / AVG_VOLUME_20`

The input must provide `Close` and `Volume`. The function does not mutate the original frame, but it does not validate ordering, frequency, numeric dtypes, duplicate timestamps, or required columns before calculation.

`calculate_extended_indicators(df) -> pandas.DataFrame` first calls `calculate_indicators()` and then adds the following columns. It is additive; the original `calculate_indicators()` output is intentionally unchanged for backward compatibility:

- `ATR_14`: 14-period Average True Range
- `BOLL_UPPER`, `BOLL_MIDDLE`, `BOLL_LOWER`: 20-period Bollinger Bands with two standard deviations
- `BOLL_WIDTH`: `(BOLL_UPPER - BOLL_LOWER) / BOLL_MIDDLE * 100`
- `ADX_14`: 14-period Average Directional Index
- `PLUS_DI`, `MINUS_DI`: 14-period positive and negative directional indicators
- `STOCH_K`, `STOCH_D`: 14-period stochastic oscillator and its three-period signal smoothing
- `CCI_20`: 20-period Commodity Channel Index
- `WILLIAMS_R`: 14-period Williams %R
- `OBV`: On-Balance Volume
- `OBV_SLOPE_5`: five-row linear slope of OBV divided by the absolute five-row mean OBV; it is a normalized per-row slope
- `VWAP_20`: rolling 20-row `sum(Close * Volume) / sum(Volume)`
- `ROC_10`: 10-period Rate of Change

The extended function uses `ta` implementations for ATR, Bollinger Bands, ADX/DI, stochastic values, CCI, Williams %R, OBV, and ROC. VWAP is only an approximation because daily OHLCV bars do not contain intraday price/volume distributions; it uses closing prices and daily volumes rather than a true session VWAP. OBV slope is hand-rolled because the required normalized rolling slope is not provided directly by `ta`.

Extended indicators require numeric `High`, `Low`, `Close`, and `Volume` columns. Rolling and warm-up periods naturally produce `NaN` values at the beginning of a frame. The function does not alter the input frame.

### `stockemailer.analysis.patterns` (`src/stockemailer/analysis/patterns.py`)

`detect_patterns(df) -> pandas.DataFrame` returns a copy of the input with per-row boolean pattern flags. It uses only OHLC data and no external pattern-recognition library. The helper functions are intentionally separate so each can be tested independently:

- `bullish_engulfing(df)`: current bullish candle engulfs the prior bearish candle
- `bearish_engulfing(df)`: current bearish candle engulfs the prior bullish candle
- `hammer(df)`: lower wick is at least twice the body and upper wick is no larger than the body
- `shooting_star(df)`: upper wick is at least twice the body and lower wick is no larger than the body
- `doji(df)`: non-zero candle range and body is less than 10% of the range
- `three_white_soldiers(df)`: three consecutive bullish candles with strictly higher closes and lower wicks no larger than their bodies
- `golden_cross(df)`: internally calculated SMA-50 crosses above SMA-200 on that row compared with the previous row
- `death_cross(df)`: internally calculated SMA-50 crosses below SMA-200 on that row compared with the previous row

The first row, and rows without enough history for a pattern, are false rather than missing. Cross flags require at least 200 rows for the SMA-200 value. Pattern detection does not call the market-data provider and does not mutate the input. `analysis.screener.analyze_stock()` invokes both `calculate_extended_indicators()` and `detect_patterns()` after downloading data, preserving all legacy result keys and adding JSON-friendly latest-row fields for every extended indicator and pattern flag. Unavailable warm-up indicator values are represented as `null` in the JSON payload rather than non-standard `NaN`; pattern flags are always boolean.

The generated report begins with a `DATA COVERAGE` block containing the latest daily-bar date found in the screened results and explicitly states that an intraday cutoff is unavailable. The email body begins with a `REPORT TIMING` block containing the extraction/report completion timestamp in India Standard Time (`Asia/Kolkata`). These are different concepts: the first describes how far the market data extends, while the second describes when this run finished.

### `stockemailer.analysis.price_targets` (`src/stockemailer/analysis/price_targets.py`)

`calculate_price_range(df, horizon_days=5, confidence=0.90) -> dict` is a pure, deterministic statistical projection. It requires a `Close` column and at least 10 valid, positive closing prices. It computes the most recent 20 daily log returns (or all available returns when history is shorter), calculates their standard deviation, scales it by `sqrt(horizon_days)`, and derives a two-sided z-score with `scipy.stats.norm.ppf((1 + confidence) / 2)`.

The returned dictionary contains rounded price fields `last_close`, `buy_zone_low`, `buy_zone_high`, `sell_target_low`, and `sell_target_high`, plus `horizon_days`, `confidence`, `sigma_daily_pct`, and method name `historical_volatility_normal_approx`. The buy zone uses a half-z pullback below the last close; the sell target uses the full z upper bound. The docstring explicitly warns that this is not a prediction or guarantee and that real markets have fat tails rather than normal-distribution returns. Invalid confidence, non-positive horizons, missing/insufficient closes, non-positive closes, or unavailable volatility raise clear `ValueError`s. The input DataFrame is never mutated and no network or random operation occurs.

### `stockemailer.analysis.screener` (`src/stockemailer/analysis/screener.py`)

#### `calculate_momentum_score(row) -> float`

The score is deterministic. The legacy thresholds contribute up to 9 points, and the retained extended confirmation signals contribute up to 8 additional points before bearish-pattern deductions.

| Signal | Condition | Points |
|---|---|---:|
| 2-day return | `RETURN_2D >= 5` | 3 |
| 2-day return | `3 <= RETURN_2D < 5` | 2 |
| 2-day return | `1 <= RETURN_2D < 3` | 1 |
| Volume | `VOLUME_RATIO >= 2` | 2 |
| Volume | `1.5 <= VOLUME_RATIO < 2` | 1.5 |
| Volume | `1.2 <= VOLUME_RATIO < 1.5` | 1 |
| RSI | `55 <= RSI <= 70` | 1 |
| Trend | `Close > SMA_20 > SMA_50` | 1 |
| MACD | `MACD > MACD_SIGNAL` | 1 |
| 5-day return | `RETURN_5D > 0` | 1 |

Scores are rounded to two decimal places. Negative or below-threshold values contribute zero. The theoretical maximum is 20: 10 legacy points plus 10 extended confirmation points.

The extended component awards points for ATR relative to close at or below 3%, Bollinger width at or below 10%, Bollinger position, ADX at or above 20, stochastic K above D, positive OBV, positive OBV slope, and close above rolling VWAP. Bullish engulfing, hammer, three white soldiers, and golden cross add confirmation; bearish engulfing, shooting star, death cross, and doji reduce confirmation. RSI remains the representative oscillator in the legacy score. Because validation found strong redundancy among RSI, `PLUS_DI`/`MINUS_DI`, CCI, Williams %R, and ROC, those correlated extended contributions were removed from scoring; their values remain calculated and reported. `SMA_200` contributes indirectly through the golden/death-cross flags.

`signal_val.json` is the current data-driven diagnostic snapshot. It found 11 feature pairs above the 0.80 absolute Spearman-correlation threshold and high VIF for RSI, CCI, Williams %R, and the directional indicators. Keep this validation report updated before changing score weights again.

`stockemailer.analysis.validation` (`src/stockemailer/analysis/validation.py`) provides data-driven diagnostics before changing these hand-picked weights. Run it with `uv run python -m stockemailer.analysis.validation --period 2y --output signal_validation.json`. It downloads daily history for the configured universe, calculates features, pairs each feature at time T with forward 1-, 5-, and 10-day returns, and reports pooled Spearman information coefficients with observation counts. It also reports a Spearman feature-correlation matrix, pairs above the configured 0.80 absolute-correlation threshold, and variance inflation factors for score-related features. Failed downloads are recorded instead of being treated as zero signal. Review this output before retuning or adding score points; the existing scorer remains deterministic and unchanged by the diagnostic run.

#### `analyze_stock(ticker) -> Optional[dict]`

For one ticker, the function downloads default history, rejects missing data or frames shorter than 50 rows, calculates indicators, and examines the latest row. It rejects the stock if any of these latest values is missing:

```text
RETURN_2D, RETURN_5D, RSI, VOLUME_RATIO,
SMA_20, SMA_50, MACD, MACD_SIGNAL
```

On success it returns a JSON-friendly dictionary with:

```text
ticker, date, close,
return_1d, return_2d, return_5d,
volume_ratio, rsi, sma_20, sma_50,
macd, macd_signal,
above_20dma, above_50dma, macd_bullish,
momentum_score, price_range
```

Prices, returns, ratios, RSI, and moving averages are rounded to two decimals. MACD values are rounded to four decimals. `date` is the last DataFrame index formatted as `YYYY-MM-DD`. Boolean flags compare the latest close or MACD values directly. `SMA_200` is neither returned nor checked for missingness.

`price_range` is a nested dictionary from `calculate_price_range()` or `null` if that calculation raises `ValueError`; this failure does not discard an otherwise valid stock analysis. Its nested keys are `last_close`, `buy_zone_low`, `buy_zone_high`, `sell_target_low`, `sell_target_high`, `horizon_days`, `confidence`, `sigma_daily_pct`, and `method`. Existing top-level keys and momentum-score point values must not change.

#### `screen_market(tickers=None, top_n=20) -> list[dict]`

Uses `NSE_STOCKS` when `tickers` is omitted. It prints scan progress, calls `analyze_stock` sequentially for every ticker, skips `None` results, sorts successful results descending by `momentum_score`, and returns at most `top_n` results. It has no explicit validation for `top_n`, ticker values, duplicate symbols, or ties.

### `stockemailer.agent.gemini_agent` (`src/stockemailer/agent/gemini_agent.py`)

Creates a module-level Gemini client with `GEMINI_API_KEY`. It defines:

- `run_stock_screener()`: calls `screen_market(top_n=20)` and returns enriched results as indented JSON. Each successful stock includes the legacy screening fields plus the latest extended-indicator values and candlestick/price-action flags produced by `analyze_stock()`.
- `screen_market_tool`: a Gemini function declaration with no arguments. Its description says it scans the configured Indian universe and returns the deterministic top 20.
- `SYSTEM_INSTRUCTION`: directs Gemini to select five candidates, use multiple confirming indicators, preserve Python's numeric values, distinguish data from interpretation, state risks, avoid guarantees, and produce the required report structure.
- `analyze_market()`: performs the Gemini interaction.

The current `analyze_market()` flow is:

1. Send the request to Gemini with the system instruction and `screen_market` tool declaration.
2. If Gemini returns no function calls, immediately return `response.text`.
3. For each requested function call named `screen_market`, execute the local Python screener and create a function-response part containing the JSON result.
4. Send a second Gemini request containing the original user request, the first response candidate content, and the tool results.
5. Return `final_response.text`.

Unknown function-call names are silently ignored. The implementation assumes the first response has a candidate with usable content and that both Gemini responses contain usable text. There is no retry, timeout, token-budget policy, response validation, numeric consistency check, or explicit handling of malformed API responses. Keep quantitative calculations in Python; Gemini should interpret validated results rather than invent market data.

The requested model output is:

```text
TOP 5 MOMENTUM STOCKS

1. Company / ticker
   Momentum score:
   2-day return:
   Volume ratio:
   RSI:
   Trend:
   MACD:
   Why it qualifies:
   Main risk:

...

MARKET OBSERVATION
```

### `stockemailer.notifications.gmail` (`src/stockemailer/notifications/gmail.py`)

Defines the Gmail OAuth and delivery boundary:

- `SCOPES`: only Gmail send permission
- `BASE_DIR`: repository root, calculated from this module's path
- `CREDENTIALS_FILE`: root `credentials.json`
- `TOKEN_FILE`: root `token.json`
- `get_gmail_service()`: loads, refreshes, or interactively creates OAuth credentials, then builds the Gmail v1 service
- `send_email(recipient, subject, body)`: creates a plain-text `MIMEText`, URL-safe base64 encodes it, and sends it with `users().messages().send(userId="me")`

The sender is the authenticated Gmail account. The message body is not HTML. Gmail API and OAuth failures currently propagate. Token writes are not atomic and do not explicitly set restrictive permissions; improve this before treating the application as production-grade.

### `stockemailer.main` (`src/stockemailer/main.py`)

`main()` is the orchestration entry point. It loads dotenv, prints a banner, calls `analyze_market`, prints the report, validates `EMAIL_RECIPIENT`, sends the report, and prints a success message. It does not catch analysis, OAuth, API, or delivery failures. Email configuration is checked only after the potentially expensive market analysis.

### `stockemailer.backtesting` (`src/stockemailer/backtesting.py`)

The standalone backtesting module evaluates the existing deterministic screener at a historical date without involving Gemini or Gmail. Backtests use 15-minute Yahoo Finance bars. Yahoo Finance limits these bars to a rolling recent window; the code clamps the download start to the newest permitted date and raises a clear `ValueError` when the requested analysis date itself is older than that window. Older dates require stored intraday data or a different provider. Run it from the repository root with:

```bash
uv run python -m stockemailer.backtesting 2024-09-16
```

Use `--output path/to/results.json` to choose a destination. Without that option, results are written to `backtest_results/backtest_<YYYY-MM-DD>.json`. The module downloads a recent 15-minute window ending shortly after the requested date, clamps the start of the real Yahoo request to Yahoo's rolling intraday retention limit, calculates indicators only on rows through the analysis date, and therefore avoids using future data when selecting stocks.

To run an inclusive range of analysis dates:

```bash
uv run python -m stockemailer.backtesting 2024-09-16 2024-09-20
```

Use `--output-dir path/to/results` to choose the directory for the individual daily files and the consolidated file. The range command writes `backtest_<date>.json` for every calendar date in the range and `backtest_<start>_to_<end>.json` containing `dates_processed`, total stocks selected, total trades evaluated, successful and failed trades, overall `success_rate_pct`, and the full `daily_results` list. Weekend or holiday dates remain represented with zero results when no market bars are available. The date loop is inclusive of both start and end dates.

The default rules are explicit and deterministic:

- Select up to the top five stocks from `NSE_STOCKS`, ranked by the existing `calculate_momentum_score()`.
- Use the requested date as the signal date; analysis is assumed to happen after that day's market close.
- Plan entry at the mean of the signal date's calculated `buy_zone_low` and `buy_zone_high`.
- Plan exit at the mean of `sell_target_low` and `sell_target_high`, capped at 0.5% above the planned entry midpoint.
- On the first subsequent trading day, consider entry possible at the first 15-minute bar whose adjusted low/high range contains the planned entry midpoint.
- Consider the exit target reached only at a later 15-minute bar whose adjusted high reaches the planned exit midpoint. The exit timestamp must be strictly later than the entry timestamp.
- If no entry bar reaches the planned entry midpoint, mark the trade `neutral`; neutral trades are excluded from evaluated/success/failure counts.
- If entry occurs but no later bar reaches the exit midpoint, mark the trade `failed`.
- If no subsequent trading-day bar is available, mark the trade `next_trading_day_unavailable` and exclude it from evaluated/success/failure counts.

`run_backtest(analysis_date, output_path=None, tickers=None, data_loader=...) -> dict` supports an injected data loader for deterministic tests. The persisted result includes the date, execution rules, selected/evaluated/successful/failed/neutral/unavailable counts, and compact per-trade records: ticker, analysis date, next trading date, momentum score, midpoint `planned_entry_price`, capped `planned_exit_price`, actual next-day OHLC, `entry_possible`, `exit_possible`, and status. A trade counts as successful only when both planned midpoint levels are reached. Neutral trades have no entry and are excluded from evaluated and failed counts. Trades whose next trading day is unavailable are also excluded from evaluated and failed counts. A `price_range` calculation failure does not invalidate a selected stock; its planned midpoint prices are `null` and its entry/exit checks are false.

This is a one-day planned-midpoint evaluation using 15-minute bars, not a full portfolio simulator. It does not model exact intrabar fills, slippage, brokerage, taxes, position sizing, capital constraints, dividends separately from adjusted prices, overlapping positions, or multi-day holding periods. Yahoo Finance also limits how far back intraday intervals can be requested, so old analysis dates may have insufficient data. Historical success is not evidence of future performance.

## Data and Integration Contracts

### Market data contract

At minimum, a provider result must be a `pandas.DataFrame` with numeric `Close` and `Volume` columns and a date-like index. The current provider may return MultiIndex columns, which are flattened before use. Downstream calculations assume chronological, non-duplicated daily rows.

### Screener result contract

The screener returns a list of dictionaries described above. These values are the authoritative quantitative results passed to Gemini. Any future consumer should treat the dictionary keys and units as an API contract: returns are percentages, volume ratio is dimensionless, prices and averages are in the instrument's currency, and MACD uses the adjusted close series from Yahoo Finance.

### Agent contract

Gemini receives a tool with no user-configurable parameters. The local tool returns top-20 JSON, while the model chooses and explains five. The model must not alter numerical values, select solely from an unverified invented list, guarantee performance, or present the output as personalized advice.

### Email contract

The delivery function accepts a recipient, subject, and plain-text body. It requires a valid Gmail OAuth client file and authorized-user token or an interactive first-run authorization. It returns no value; successful delivery is indicated by its print statement.

## Known Limitations and Risks

- The console script is wired to the placeholder package-level function.
- The README provides no setup or operational guidance.
- There is no automated test suite, CI, fixture data, or deterministic replay path.
- Network scanning is sequential and can be slow or fail partially.
- Yahoo Finance data has no retry, timeout, freshness, schema, or rate-limit safeguards.
- A 50-row minimum is enforced even though a 200-period SMA is calculated; `SMA_200` is currently unused.
- Missing email configuration is discovered after Gemini and market-data work.
- Gemini response shape and tool-call behavior are assumed rather than validated.
- Unknown Gemini tools are ignored.
- There is no check that the model preserved Python's quantitative values.
- Gmail authentication may require a browser and is not naturally suited to unattended scheduling.
- OAuth token persistence lacks explicit permission hardening and atomic replacement.
- `test_email.py` sends a real message as a module side effect.
- `print` statements are the only observability mechanism.
- There is no duplicate-send prevention, scheduling, timezone policy, trading-calendar policy, or idempotency key.
- The fixed universe may become stale and has no sector or liquidity controls.
- The application does not account for transaction costs, slippage, corporate actions beyond Yahoo's adjusted data, or investment suitability.

## Development Rules for Future LLMs

1. Read the local module and its neighboring tests/callers before editing. Keep changes small and focused.
2. Preserve the layer boundaries: provider-specific code in `data`, deterministic calculations in `analysis`, model orchestration in `agent`, and Gmail concerns in `notifications`.
3. Keep quantitative signals deterministic, typed, and testable outside Gemini. Never make the LLM the source of market numbers.
4. Preserve units, key names, rounding rules, and score semantics unless the change explicitly updates the contract and documentation.
5. Validate external data before indicator computation. Prefer explicit, actionable exceptions or structured skip reasons over silent corruption.
6. Avoid import-time network calls and side effects. In particular, never make importing a module send an email.
7. Validate all required configuration before expensive work and never log secrets, OAuth payloads, tokens, or complete API keys.
8. Keep credentials local and ignored. Do not add real `.env`, `credentials.json`, or `token.json` contents to examples, tests, patches, or commits.
9. Add tests for scoring boundaries, indicator columns, missing/short data, sorting/top-N behavior, tool-call handling, and email MIME encoding as each area changes.
10. Mock Yahoo Finance, Gemini, and Gmail in tests. Tests must not make live network requests or send real email.
11. Use fixtures or recorded data for deterministic analysis tests. Include tests for malformed frames, missing columns, NaN latest values, empty downloads, and provider failures.
12. Keep user-facing financial language cautious: describe observed historical signals and risks, not predictions or guarantees.
13. Update `README.md` and this file when setup, commands, environment variables, output schemas, integrations, or operational behavior change.
14. Run focused tests first, then the full test suite and a package/entry-point smoke check. Do not claim live delivery succeeded unless a real delivery was intentionally performed.
15. Do not perform unrelated refactors, dependency upgrades, formatting churn, commits, or destructive Git operations as part of a focused feature.

## Recommended Improvement Order

When developing this project further, the most valuable sequence is:

1. Fix the console entry point and add a safe, documented CLI path.
2. Add configuration validation for all required settings before analysis begins.
3. Convert `test_email.py` into an explicit smoke-test command with no import-time send.
4. Add unit tests with mocked network boundaries and deterministic market-data fixtures.
5. Add market-data schema validation, retry/timeout policy, and structured skip/error reporting.
6. Make universe, period, interval, top-N, and recipient behavior configurable without weakening defaults.
7. Validate Gemini tool calls and responses, and enforce numeric consistency against screener results.
8. Harden token persistence and design a non-interactive authentication path for scheduled runs.
9. Add structured logging, run identifiers, idempotency/duplicate-send protection, and explicit timezone/trading-day behavior.
10. Document deployment, scheduling, monitoring, and financial-risk boundaries.

## Validation Checklist

Before considering a future change complete:

- `uv sync` succeeds with the supported Python version.
- Imports do not unexpectedly call external services or send mail.
- Indicator calculations preserve the expected columns and units.
- Score threshold tests cover exact boundary values.
- Screen results are deterministic for fixed input fixtures.
- Yahoo Finance, Gemini, and Gmail are mocked in automated tests.
- Missing configuration fails with a clear non-secret message.
- No secret files or values appear in Git changes, logs, fixtures, or documentation.
- The real module entry point and declared console command both invoke the intended workflow.
- Generated reports preserve quantitative values and include cautious research language.
- Email is sent only after explicit orchestration and successful analysis.
