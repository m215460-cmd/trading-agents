
import sqlite3
import json
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

INITIAL_CAPITAL = 20000.0
COMMISSION_RATE = 0.0005
MAX_POSITION_VALUE = 2000.0
MAX_DAILY_LOSS = 600.0

MOSCOW = ZoneInfo("Europe/Moscow")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connect(path):
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=15000")
    return con


def valid_number(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value):
        return False
    return value > 0 if positive else True


def valid_symbol(symbol):
    return (
        isinstance(symbol, str)
        and 1 <= len(symbol) <= 20
        and symbol.replace("_", "").isalnum()
    )


def init_db(path):
    con = connect(path)

    con.execute("""
        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS paper_positions (
            symbol TEXT PRIMARY KEY,
            qty REAL NOT NULL,
            avg_price REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS paper_portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cash REAL NOT NULL,
            initial_capital REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            commission REAL NOT NULL,
            realized_pnl REAL NOT NULL DEFAULT 0,
            note TEXT
        )
    """)

    row = con.execute(
        "SELECT id FROM paper_portfolio WHERE id=1"
    ).fetchone()

    if not row:
        now = utc_now()
        con.execute(
            "INSERT INTO paper_portfolio "
            "(id,cash,initial_capital,created_at,updated_at) "
            "VALUES (1,?,?,?,?)",
            (INITIAL_CAPITAL, INITIAL_CAPITAL, now, now)
        )

    con.commit()
    con.close()


def save_cycle(path, result):
    con = connect(path)
    try:
        con.execute(
            "INSERT INTO cycles(ts,result_json) VALUES (?,?)",
            (utc_now(), json.dumps(result, ensure_ascii=False))
        )
        con.commit()
    finally:
        con.close()


def daily_realized_pnl(path):
    con = connect(path)
    try:
        today = datetime.now(MOSCOW).date().isoformat()

        rows = con.execute(
            "SELECT ts,realized_pnl FROM paper_trades "
            "WHERE side='SELL'"
        ).fetchall()

        total = 0.0

        for row in rows:
            ts = row["ts"]
            try:
                trade_date = datetime.fromisoformat(ts).astimezone(
                    MOSCOW
                ).date().isoformat()
            except Exception:
                trade_date = ts[:10]

            if trade_date == today:
                total += row["realized_pnl"]

        return total
    finally:
        con.close()


def daily_realized_loss(path):
    return max(0.0, -daily_realized_pnl(path))


def portfolio_value(path, prices=None):
    prices = prices or {}
    con = connect(path)

    try:
        portfolio = con.execute(
            "SELECT cash,initial_capital FROM paper_portfolio "
            "WHERE id=1"
        ).fetchone()

        positions = con.execute(
            "SELECT symbol,qty,avg_price,updated_at "
            "FROM paper_positions"
        ).fetchall()

        if not portfolio:
            return {"error": "Portfolio not initialized"}

        position_value = 0.0
        unrealized_pnl = 0.0
        items = []

        for p in positions:
            symbol = p["symbol"]
            qty = p["qty"]
            avg = p["avg_price"]

            price = prices.get(symbol, avg)

            if not valid_number(price, positive=True):
                price = avg

            value = qty * price
            pnl = qty * (price - avg)

            position_value += value
            unrealized_pnl += pnl

            items.append({
                "symbol": symbol,
                "qty": qty,
                "avg_price": avg,
                "mark_price": price,
                "value": value,
                "unrealized_pnl": pnl
            })

        cash = portfolio["cash"]

        return {
            "mode": "PAPER_ONLY",
            "initial_capital": portfolio["initial_capital"],
            "cash": cash,
            "position_value": position_value,
            "equity": cash + position_value,
            "unrealized_pnl": unrealized_pnl,
            "daily_realized_loss": daily_realized_loss(path),
            "positions": items,
            "limits": {
                "max_position_value": MAX_POSITION_VALUE,
                "max_daily_loss": MAX_DAILY_LOSS,
                "commission_rate": COMMISSION_RATE
            }
        }
    finally:
        con.close()


def paper_buy(path, symbol, price, qty=None):
    if not valid_symbol(symbol):
        return {"status": "rejected", "reason": "Invalid symbol"}

    if not valid_number(price, positive=True):
        return {"status": "rejected", "reason": "Invalid price"}

    if qty is not None and not valid_number(qty, positive=True):
        return {"status": "rejected", "reason": "Invalid quantity"}

    con = connect(path)

    try:
        con.execute("BEGIN IMMEDIATE")

        portfolio = con.execute(
            "SELECT cash,initial_capital FROM paper_portfolio "
            "WHERE id=1"
        ).fetchone()

        if not portfolio:
            con.rollback()
            return {"status": "rejected", "reason": "Portfolio missing"}

        cash = portfolio["cash"]

        realized_loss = daily_realized_loss(path)

        if realized_loss >= MAX_DAILY_LOSS:
            con.rollback()
            return {
                "status": "rejected",
                "reason": "Daily realized loss limit reached"
            }

        current = con.execute(
            "SELECT qty,avg_price FROM paper_positions "
            "WHERE symbol=?",
            (symbol,)
        ).fetchone()

        current_qty = current["qty"] if current else 0.0
        current_avg = current["avg_price"] if current else 0.0

        current_value = current_qty * price
        remaining_limit = MAX_POSITION_VALUE - current_value

        if remaining_limit <= 0:
            con.rollback()
            return {"status": "rejected", "reason": "Position limit reached"}

        max_qty_by_limit = math.floor(remaining_limit / price)
        max_qty_by_cash = math.floor(
            cash / (price * (1 + COMMISSION_RATE))
        )

        allowed_qty = min(max_qty_by_limit, max_qty_by_cash)

        if qty is not None:
            allowed_qty = min(allowed_qty, math.floor(qty))

        if allowed_qty <= 0:
            con.rollback()
            return {
                "status": "rejected",
                "reason": "Insufficient cash or position limit"
            }

        cost = allowed_qty * price
        commission = cost * COMMISSION_RATE
        total = cost + commission

        new_qty = current_qty + allowed_qty

        # Purchase commission is included in position cost basis.
        new_avg = (
            (current_qty * current_avg + cost + commission) / new_qty
        )

        now = utc_now()

        con.execute(
            "INSERT INTO paper_positions "
            "(symbol,qty,avg_price,updated_at) "
            "VALUES(?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET "
            "qty=excluded.qty,avg_price=excluded.avg_price,"
            "updated_at=excluded.updated_at",
            (symbol, new_qty, new_avg, now)
        )

        con.execute(
            "UPDATE paper_portfolio SET cash=?,updated_at=? "
            "WHERE id=1",
            (cash - total, now)
        )

        con.execute(
            "INSERT INTO paper_trades "
            "(ts,symbol,side,qty,price,commission,realized_pnl,note) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (now, symbol, "BUY", allowed_qty, price,
             commission, 0.0, "Paper execution")
        )

        con.commit()

        return {
            "status": "executed_paper",
            "symbol": symbol,
            "qty": allowed_qty,
            "price": price,
            "commission": commission,
            "total": total,
            "cash_remaining": cash - total
        }

    except Exception as e:
        con.rollback()
        return {"status": "error", "reason": str(e)}

    finally:
        con.close()


def paper_sell(path, symbol, price, qty=None):
    if not valid_symbol(symbol):
        return {"status": "rejected", "reason": "Invalid symbol"}

    if not valid_number(price, positive=True):
        return {"status": "rejected", "reason": "Invalid price"}

    if qty is not None and not valid_number(qty, positive=True):
        return {"status": "rejected", "reason": "Invalid quantity"}

    con = connect(path)

    try:
        con.execute("BEGIN IMMEDIATE")

        portfolio = con.execute(
            "SELECT cash FROM paper_portfolio WHERE id=1"
        ).fetchone()

        position = con.execute(
            "SELECT qty,avg_price FROM paper_positions "
            "WHERE symbol=?",
            (symbol,)
        ).fetchone()

        if not portfolio or not position:
            con.rollback()
            return {"status": "rejected", "reason": "Position not found"}

        available_qty = position["qty"]

        sell_qty = (
            math.floor(available_qty)
            if qty is None
            else min(math.floor(qty), math.floor(available_qty))
        )

        if sell_qty <= 0:
            con.rollback()
            return {"status": "rejected", "reason": "Invalid quantity"}

        avg_price = position["avg_price"]

        proceeds = sell_qty * price
        commission = proceeds * COMMISSION_RATE
        net_proceeds = proceeds - commission

        # avg_price already includes the buy commission.
        realized_pnl = sell_qty * (price - avg_price) - commission

        now = utc_now()
        remaining = available_qty - sell_qty

        if remaining <= 1e-9:
            con.execute(
                "DELETE FROM paper_positions WHERE symbol=?",
                (symbol,)
            )
        else:
            con.execute(
                "UPDATE paper_positions SET qty=?,updated_at=? "
                "WHERE symbol=?",
                (remaining, now, symbol)
            )

        con.execute(
            "UPDATE paper_portfolio SET cash=cash+?,updated_at=? "
            "WHERE id=1",
            (net_proceeds, now)
        )

        con.execute(
            "INSERT INTO paper_trades "
            "(ts,symbol,side,qty,price,commission,realized_pnl,note) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (now, symbol, "SELL", sell_qty, price, commission,
             realized_pnl, "Paper execution")
        )

        con.commit()

        return {
            "status": "executed_paper",
            "symbol": symbol,
            "qty": sell_qty,
            "price": price,
            "commission": commission,
            "realized_pnl": realized_pnl,
            "cash_after": portfolio["cash"] + net_proceeds
        }

    except Exception as e:
        con.rollback()
        return {"status": "error", "reason": str(e)}

    finally:
        con.close()


def latest_report(path):
    con = connect(path)

    try:
        row = con.execute(
            "SELECT ts,result_json FROM cycles ORDER BY id DESC LIMIT 1"
        ).fetchone()

        count = con.execute(
            "SELECT COUNT(*) FROM cycles"
        ).fetchone()[0]

        positions = con.execute(
            "SELECT symbol,qty,avg_price,updated_at "
            "FROM paper_positions"
        ).fetchall()

        trades = con.execute(
            "SELECT id,ts,symbol,side,qty,price,commission,"
            "realized_pnl,note FROM paper_trades "
            "ORDER BY id DESC LIMIT 50"
        ).fetchall()

        portfolio = con.execute(
            "SELECT cash,initial_capital,created_at,updated_at "
            "FROM paper_portfolio WHERE id=1"
        ).fetchone()

        return {
            "cycles_count": count,
            "latest_cycle": json.loads(row["result_json"]) if row else None,
            "latest_cycle_time": row["ts"] if row else None,
            "paper_positions": [dict(p) for p in positions],
            "paper_trades": [dict(t) for t in trades],
            "portfolio": dict(portfolio) if portfolio else None,
            "mode": "PAPER_ONLY"
        }
    finally:
        con.close()
