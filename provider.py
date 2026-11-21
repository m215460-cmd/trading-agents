
import json
import urllib.request
from datetime import datetime, timezone

TICKERS = ["SBER", "LKOH", "YDEX", "ROSN", "GMKN", "OZON", "VTBR", "T"]


def get_market_snapshot():
    quotes = []
    errors = []

    for ticker in TICKERS:
        try:
            url = (
                f"https://iss.moex.com/iss/engines/stock/"
                f"markets/shares/securities/{ticker}.json?"
                "iss.only=marketdata,securities&"
                "marketdata.columns=SECID,BOARDID,LAST,LCURRENTPRICE,"
                "MARKETPRICE,TRADEDATE,TRADETIME&"
                "securities.columns=SECID,PREVPRICE"
            )

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TradingAgents/2.0"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            md = data.get("marketdata", {})
            sec = data.get("securities", {})

            md_columns = md.get("columns", [])
            md_rows = md.get("data", [])

            sec_columns = sec.get("columns", [])
            sec_rows = sec.get("data", [])

            if not md_rows:
                errors.append({"ticker": ticker, "error": "No marketdata rows"})
                continue

            md_item = dict(zip(md_columns, md_rows[0]))
            sec_item = dict(zip(sec_columns, sec_rows[0])) if sec_rows else {}

            price = (
                md_item.get("LAST")
                or md_item.get("LCURRENTPRICE")
                or md_item.get("MARKETPRICE")
            )

            previous = sec_item.get("PREVPRICE")

            if price is None or float(price) <= 0:
                errors.append({"ticker": ticker, "error": "Invalid price"})
                continue

            quotes.append({
                "ticker": ticker,
                "price": float(price),
                "previous": float(previous) if previous is not None else None,
                "board": md_item.get("BOARDID"),
                "trade_date": md_item.get("TRADEDATE"),
                "trade_time": md_item.get("TRADETIME")
            })

        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

    valid = [q for q in quotes if q.get("price") is not None]

    return {
        "status": "ok" if valid else "no_verified_quotes",
        "source": "MOEX ISS",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "quotes": valid,
        "errors": errors
    }
