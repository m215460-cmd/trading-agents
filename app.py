from fastapi import FastAPI
import os

from agents import run_committee
from ledger import init_db, latest_report
from provider import get_market_snapshot

app = FastAPI(title="Trading Agents v2 - PAPER ONLY")

DB = os.getenv("DB_PATH", "ledger.db")
init_db(DB)


@app.get("/")
def home():
    return {
        "system": "Trading Agents v2",
        "mode": "PAPER_ONLY",
        "real_orders": False,
        "status": "online",
        "agents": ["Bull", "Bear", "Owl", "Director"]
    }


@app.get("/health")
def health():
    snapshot = get_market_snapshot()

    return {
        "status": "ready",
        "mode": "PAPER_ONLY",
        "real_orders": False,
        "data_provider": snapshot.get("status"),
        "source": snapshot.get("source"),
        "as_of": snapshot.get("as_of"),
        "agent_count": 5
    }


@app.get("/market")
def market():
    return get_market_snapshot()


@app.get("/cycle")
def cycle():
    snapshot = get_market_snapshot()

    if snapshot.get("status") != "ok" or not snapshot.get("quotes"):
        return {
            "decision": "NO TRADE",
            "reason": "Verified market data unavailable",
            "mode": "PAPER_ONLY",
            "real_orders": False,
            "snapshot": snapshot
        }

    return run_committee(DB)


@app.get("/report")
def report():
    return latest_report(DB)


@app.get("/safety")
def safety():
    return {
        "mode": "PAPER_ONLY",
        "real_orders": False,
        "live_trading_enabled": False,
        "leverage_enabled": False,
        "withdrawals_enabled": False
    }
