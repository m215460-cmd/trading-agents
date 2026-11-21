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
    return {
        "status": "ready",
        "mode": "PAPER_ONLY",
        "data_provider": "MOEX ISS",
        "real_orders": False,
        "agent_count": 4
    }


@app.get("/market")
def market():
    return get_market_snapshot()


@app.get("/cycle")
def cycle():
    return run_committee(DB)


@app.get("/report")
def report():
    return latest_report(DB)
