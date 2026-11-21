import sqlite3, json
from datetime import datetime, timezone

def init_db(path):
    con=sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS cycles (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, result_json TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS paper_positions (symbol TEXT PRIMARY KEY, qty REAL NOT NULL, avg_price REAL NOT NULL, updated_at TEXT NOT NULL)")
    con.commit(); con.close()

def save_cycle(path,result):
    con=sqlite3.connect(path)
    con.execute("INSERT INTO cycles(ts,result_json) VALUES (?,?)",(datetime.now(timezone.utc).isoformat(),json.dumps(result,ensure_ascii=False)))
    con.commit(); con.close()

def latest_report(path):
    con=sqlite3.connect(path)
    row=con.execute("SELECT ts,result_json FROM cycles ORDER BY id DESC LIMIT 1").fetchone()
    count=con.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
    positions=con.execute("SELECT symbol,qty,avg_price,updated_at FROM paper_positions").fetchall()
    con.close()
    return {"cycles_count":count,"latest_cycle":json.loads(row[1]) if row else None,"latest_cycle_time":row[0] if row else None,"paper_positions":positions,"mode":"PAPER_ONLY"}
