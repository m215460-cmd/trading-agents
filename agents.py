from datetime import datetime, timezone
from provider import get_market_snapshot
from ledger import save_cycle

def run_committee(db_path):
    snapshot=get_market_snapshot()
    timestamp=datetime.now(timezone.utc).isoformat()
    if snapshot.get("status")!="ok" or not snapshot.get("quotes"):
        result={
            "time":timestamp,
            "status":"blocked_no_verified_market_data",
            "mode":"PAPER_ONLY",
            "agents":{
                "Bull":"No verified quote data; no candidate thesis.",
                "Bear":"VETO: data-integrity risk.",
                "Owl":"Technical analysis withheld; data missing.",
                "Market Regime":"UNKNOWN; risk state cannot be established.",
                "Director":"NO TRADE. Missing verified market data."
            },
            "decision":"NO TRADE",
            "snapshot":snapshot
        }
        save_cycle(db_path,result)
        return result

    # Strategy and data-quality checks not yet implemented; fail closed.
    result={"time":timestamp,"status":"strategy_not_implemented","decision":"NO TRADE","mode":"PAPER_ONLY"}
    save_cycle(db_path,result)
    return result
