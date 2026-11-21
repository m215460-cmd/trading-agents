
from datetime import datetime, timezone
from provider import get_market_snapshot
from ledger import save_cycle

# PAPER ONLY: analytical committee, no real orders.
MAX_CANDIDATES = 2
MIN_CHANGE_PCT = 0.50
MAX_CHANGE_PCT = 5.0


def run_committee(db_path):
    snapshot = get_market_snapshot()
    timestamp = datetime.now(timezone.utc).isoformat()

    if snapshot.get("status") != "ok" or not snapshot.get("quotes"):
        result = {
            "time": timestamp,
            "status": "blocked_no_verified_market_data",
            "mode": "PAPER_ONLY",
            "decision": "NO TRADE",
            "agents": {
                "Bull": "No verified quotes.",
                "Bear": "VETO: data integrity.",
                "Owl": "Analysis unavailable.",
                "Risk Manager": "BLOCKED.",
                "Director": "NO TRADE."
            },
            "snapshot": snapshot
        }
        save_cycle(db_path, result)
        return result

    analyses = []
    candidates = []

    for q in snapshot["quotes"]:
        ticker = q.get("ticker")
        price = q.get("price")
        previous = q.get("previous")

        if not ticker or not isinstance(price, (int, float)):
            continue

        if not isinstance(previous, (int, float)) or previous <= 0:
            analyses.append({
                "ticker": ticker,
                "status": "rejected",
                "reason": "Missing previous price"
            })
            continue

        change_pct = (price / previous - 1) * 100

        # Reject extreme moves until data and strategy are validated.
        if abs(change_pct) > MAX_CHANGE_PCT:
            analyses.append({
                "ticker": ticker,
                "price": price,
                "change_pct": round(change_pct, 3),
                "status": "rejected",
                "reason": "Extreme move; manual validation required"
            })
            continue

        bull = change_pct >= MIN_CHANGE_PCT
        bear = change_pct <= -MIN_CHANGE_PCT

        owl = {
            "price": price,
            "previous": previous,
            "change_pct": round(change_pct, 3),
            "direction": "UP" if change_pct > 0 else (
                "DOWN" if change_pct < 0 else "FLAT"
            )
        }

        risk = {
            "approved": bull and not bear,
            "reason": "Momentum threshold passed" if bull else (
                "Insufficient positive momentum"
            )
        }

        item = {
            "ticker": ticker,
            "price": price,
            "change_pct": round(change_pct, 3),
            "Bull": "BUY CANDIDATE" if bull else "NO SIGNAL",
            "Bear": "VETO" if bear else "NO VETO",
            "Owl": owl,
            "Risk Manager": risk,
            "status": "candidate" if risk["approved"] else "rejected"
        }

        analyses.append(item)

        if risk["approved"]:
            candidates.append(item)

    candidates.sort(
        key=lambda x: x["change_pct"],
        reverse=True
    )

    selected = candidates[:MAX_CANDIDATES]

    result = {
        "time": timestamp,
        "mode": "PAPER_ONLY",
        "status": "analysis_complete",
        "decision": "BUY CANDIDATES" if selected else "NO TRADE",
        "agents": {
            "Bull": "Selected positive momentum candidates.",
            "Bear": "Rejected negative momentum and flagged risk.",
            "Owl": "Calculated price change versus previous price.",
            "Risk Manager": (
                "Limited candidates; no execution or capital allocation."
            ),
            "Director": (
                "Selected candidates based on the defined rules."
                if selected else "NO TRADE."
            )
        },
        "candidates": selected,
        "analysis": analyses,
        "snapshot": snapshot,
        "limitations": [
            "No historical technical indicators.",
            "No portfolio sizing or order execution.",
            "Previous price comparison is not a validated strategy.",
            "No profitability claims."
        ]
    }

    save_cycle(db_path, result)
    return result
