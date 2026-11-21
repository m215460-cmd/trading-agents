import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

TICKERS = ["SBER", "LKOH", "YDEX", "ROSN", "GMKN", "OZON", "VTBR", "T"]

def get_market_snapshot():
    quotes = []

    for ticker in TICKERS:
        try:
            url = (
                f"https://iss.moex.com/iss/engines/stock/"
                f"markets/shares/securities/{ticker}.json?"
                "iss.only=marketdata&"
                "iss.columns=SECID,BOARDID,LAST,LCURRENTPRICE,"
                "MARKETPRICE,PREVPRICE,TRADEDATE,TRADETIME"
            )

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TradingAgents/1.0"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            block = data.get("marketdata", {})
            columns = block.get("columns", [])
            rows = block.get("data", [])

            if not rows:
                continue

            row = rows[0]
            item = dict(zip(columns, row))

            price = (
                item.get("LAST")
                or item.get("LCURRENTPRICE")
                or item.get("MARKETPRICE")
            )

            if price is None or price <= 0:
                continue

            quotes.append({
                "ticker": ticker,
                "price": float(price),
                "previous": item.get("PREVPRICE"),
                "board": item.get("BOARDID"),
                "trade_date": item.get("TRADEDATE"),
                "trade_time": item.get("TRADETIME")
            })

        except Exception as e:
            quotes.append({
                "ticker": ticker,
                "error": str(e)
            })

    valid = [q for q in quotes if "price" in q]

    return {
        "status": "ok" if valid else "no_verified_quotes",
        "source": "MOEX ISS",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "quotes": valid,
        "errors": [q for q in quotes if "error" in q]
    }
