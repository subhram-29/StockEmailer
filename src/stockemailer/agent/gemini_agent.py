import json

from google import genai
from google.genai import types

from stockemailer.config import GEMINI_API_KEY, GEMINI_MODEL
from stockemailer.analysis.screener import screen_market


client = genai.Client(
    api_key=GEMINI_API_KEY
)

latest_market_data_date: str | None = None


def run_stock_screener():
    """
    Tool exposed to Gemini.
    """

    global latest_market_data_date

    results = screen_market(
        top_n=20
    )

    latest_market_data_date = max(
        (result["date"] for result in results),
        default=None,
    )

    return json.dumps(
        results,
        indent=2
    )


screen_market_tool = types.FunctionDeclaration(
    name="screen_market",
    description=(
        "Scans the configured Indian stock universe using "
        "Yahoo Finance market data and calculates technical "
        "momentum indicators. Returns the top 20 stocks ranked "
        "by deterministic momentum score."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={},
        required=[],
    ),
)


SYSTEM_INSTRUCTION = """
You are an Indian stock market momentum research agent.

Your job is to identify the 5 stocks showing the strongest
confirmed short-term upward momentum.

IMPORTANT:

The quantitative screening is performed by Python.
Do not invent or modify numerical values returned by the
screen_market tool.

The price_range fields (buy_zone_low, buy_zone_high,
sell_target_low, sell_target_high, confidence, horizon_days,
and sigma_daily_pct) are already computed by Python. Report
them verbatim. Never recalculate, round, adjust, or otherwise
modify them. If price_range is null for a stock, state exactly
"insufficient historical data for a price range" for that stock.

When asked to find today's strongest stocks:

1. Call screen_market.
2. Examine the returned top 20 candidates.
3. Select the 5 strongest candidates.
4. Explain why each candidate is attractive from a momentum
   perspective.
5. Pay particular attention to:
   - 2-day return
   - volume expansion
   - RSI
   - moving-average alignment
   - MACD
   - 5-day momentum
    - ATR and Bollinger Bands
    - ADX and directional indicators
    - stochastic, CCI, Williams %R, and ROC
    - OBV trend and rolling VWAP
    - candlestick and price-action pattern flags

Do NOT select stocks solely based on their 2-day return.

Prefer stocks where multiple independent indicators confirm
the upward movement.

Clearly distinguish quantitative signals from your interpretation.

Do not guarantee future returns.

This is market research, not personalized financial advice.

Return the result as a fixed-width, plain-text ASCII table. Do
not use Markdown tables, pipe characters, or bold markers. Use
spaces and dashes for alignment, following this structure:

Ticker       Score  2D Ret%  Buy Zone         Sell Target      Conf   Horizon
-----------  -----  -------  ---------------  ---------------  -----  -------
RELIANCE.NS  8.50    4.20   2830.10-2860.50  2860.50-2921.80  90%    5d

Include the five selected stocks in the table. Print this exact
disclaimer once directly under the table:

Price ranges are statistical projections from historical volatility (not predictions or guarantees). This is market research, not personalized financial advice.

After the table, explain each selected stock with its quantitative
signals, why it qualifies, and its main risk. Keep all values from
Python verbatim. Include a short MARKET OBSERVATION and retain the
data source and coverage note.

The explanatory section should follow this structure:

TOP 5 MOMENTUM STOCKS

1. Company / ticker
   Momentum score:
   2-day return:
   Volume ratio:
   RSI:
   Trend:
   MACD:
    Extended indicators:
    Pattern flags:
   Why it qualifies:
   Main risk:

2. ...

Finally provide:

MARKET OBSERVATION

A short summary of what the overall momentum screen indicates.
"""


def analyze_market():

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            "Analyze today's Indian market and identify "
            "the five strongest upward momentum stocks."
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[
                types.Tool(
                    function_declarations=[
                        screen_market_tool
                    ]
                )
            ],
        ),
    )

    # Check whether Gemini requested a function call
    if not response.function_calls:
        return response.text

    tool_results = []

    for function_call in response.function_calls:

        if function_call.name == "screen_market":

            result = run_stock_screener()

            tool_results.append(
                types.Part.from_function_response(
                    name="screen_market",
                    response={
                        "result": result
                    },
                )
            )

    final_response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=(
                            "Analyze today's Indian market and "
                            "identify the five strongest upward "
                            "momentum stocks."
                        )
                    )
                ],
            ),
            response.candidates[0].content,
            types.Content(
                role="user",
                parts=tool_results,
            ),
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )

    data_coverage = (
        "DATA COVERAGE\n"
        f"Market data through: {latest_market_data_date or 'unavailable'} "
        "(latest daily bar; Yahoo Finance)\n"
        "Intraday cutoff: unavailable because the source data is daily.\n\n"
    )

    return data_coverage + final_response.text