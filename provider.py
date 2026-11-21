
import json
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TICKERS = ["SBER", "LKOH", "YDEX", "ROSN", "GMKN", "OZON", "VTBR", "T"]
BOARD = "TQBR"
MAX_QUOTE_AGE_MINUTES = 30
MOSCOW = ZoneInfo("Europe/Moscow")


def get_market_snapshot():
    quotes = []
    errors = []
    now = datetime.now(timezone.utc)
    now_moscow = now.astimezone(MOSCOW)

    # Regular weekday session filter (Moscow time).
    weekday = now_moscow.weekday() < 5
    session_time = (
        now_moscow.hour > 10 or
        (now_moscow.hour == 10 and now_moscow.minute >= 0)
    ) and (
        now_moscow.hour < 18 or
        (now_moscow.hour == 18 and now_moscow.minute <= 50)
    )

    session_active = weekday and session_time

    for ticker in TICKERS:
        try:
            url = (
                f"https://iss.moex.com/iss/engines/stock/"
                f"markets/shares/securities/{ticker}.json?"
                "iss.only=marketdata,securities&"
                "marketdata.columns=SECID,BOARDID,LAST,MARKETPRICE,"
                "PREVPRICE,TRADEDATE,TRADETIME,TIME&"
                "securities.columns=SECID,PREVPRICE"
            )

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TradingAgents/3.1"}
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
                errors.append({"ticker": ticker, "error": "No market data"})
                continue

            board_rows = [
                dict(zip(md_columns, row))
                for row in md_rows
                if dict(zip(md_columns, row)).get("BOARDID") == BOARD
            ]

            if not board_rows:
                errors.append({
                    "ticker": ticker,
                    "error": f"No quote on board {BOARD}"
                })
                continue

            item = board_rows[0]
            sec_item = dict(zip(sec_columns, sec_rows[0])) if sec_rows else {}

            price = item.get("LAST")
            if price is None:
                price = item.get("MARKETPRICE")

            previous = item.get("PREVPRICE")
            if previous is None:
                previous = sec_item.get("PREVPRICE")

            if price is None or float(price) <= 0:
                errors.append({"ticker": ticker, "error": "Invalid price"})
                continue

            trade_date = item.get("TRADEDATE")
            trade_time = item.get("TRADETIME") or item.get("TIME")
            quote_time = None
            age_minutes = None

            if trade_time:
                date_for_quote = trade_date or now_moscow.strftime("%Y-%m-%d")

                try:
                    local_time = datetime.strptime(
                        f"{date_for_quote} {trade_time}",
                        "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=MOSCOW)

                    quote_time = local_time.astimezone(timezone.utc)
                    age_minutes = (now - quote_time).total_seconds() / 60

                except ValueError:
                    quote_time = None

            fresh = (
                session_active
                and quote_time is not None
                and -2 <= age_minutes <= MAX_QUOTE_AGE_MINUTES
            )

            quotes.append({
                "ticker": ticker,
                "price": float(price),
                "previous": float(previous) if previous is not None else None,
                "board": BOARD,
                "trade_date": trade_date,
                "trade_time": trade_time,
                "quote_time_utc": quote_time.isoformat() if quote_time else None,
                "age_minutes": round(age_minutes, 2) if age_minutes is not None else None,
                "fresh": fresh
            })

        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

    valid = [q for q in quotes if q.get("price") is not None]
    fresh_quotes = [q for q in valid if q.get("fresh")]

    return {
        "status": "ok" if fresh_quotes else "no_fresh_quotes",
        "source": "MOEX ISS",
        "board": BOARD,
        "as_of": now.isoformat(),
        "market_data_valid": bool(fresh_quotes),
        "session_active": session_active,
        "quotes": valid,
        "fresh_quotes": fresh_quotes,
        "errors": errors,
        "rules": {
            "required_board": BOARD,
            "max_quote_age_minutes": MAX_QUOTE_AGE_MINUTES,
            "weekday_session_only": True,
            "stale_quotes_block_trading": True
        }
    }
