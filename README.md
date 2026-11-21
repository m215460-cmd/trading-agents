# Trading Agents v2 — five-agent paper-trading scaffold

**Status: scaffold only. Not live, not connected to broker or market-data APIs.**

## Five agents
1. Bull — upside thesis/candidate analysis.
2. Bear — downside risks and veto.
3. Owl — quantitative/technical validation.
4. Market Regime — independent market-wide risk state (GREEN/YELLOW/RED/UNKNOWN).
5. Director — portfolio decision; can always choose NO TRADE.

## Safety
- Paper-only; no real orders or broker connection.
- No fabricated prices: provider returns `not_configured`.
- No strategy signals until data is connected and strategy implemented/tested.
- Missing/stale/invalid data => NO TRADE.
- No leverage or derivatives planned.

## Local start
Python 3.11+
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080
```
Endpoints:
- `/health` — status
- `/cycle` — one committee cycle (currently blocked due to no market data)
- `/report` — ledger/report

This is an initial code skeleton only. Do not use for financial decisions.
