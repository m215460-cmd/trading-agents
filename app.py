from fastapi import FastAPI
import os
from agents import run_committee
from ledger import init_db, latest_report

app=FastAPI(title="Trading Agents v2 — paper mode")
DB=os.getenv("DB_PATH","ledger.db")
init_db(DB)

@app.get("/health")
def health():
    return {"status":"scaffold_ready","mode":"PAPER_ONLY","data_provider":"not_configured","real_orders":False,"agent_count":5}

@app.get("/cycle")
def cycle():
    return run_committee(DB)

@app.get("/report")
def report():
    return latest_report(DB)
