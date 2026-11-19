import sqlite3
from datetime import datetime
import json

DB_NAME = "trading_signals.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            display_name TEXT NOT NULL,
            category TEXT NOT NULL,
            action TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            tp1 REAL NOT NULL,
            tp2 REAL NOT NULL,
            confidence INTEGER NOT NULL,
            ai_analysis TEXT NOT NULL,
            tech_reasons TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_signal(data: dict):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # تجنب تكرار نفس التوصية لنفس الزوج في أقل من 30 دقيقة
    c.execute('''
        SELECT id FROM signals 
        WHERE symbol = ? AND action = ? AND status = 'ACTIVE'
        ORDER BY id DESC LIMIT 1
    ''', (data['symbol'], data['action']))
    existing = c.fetchone()
    
    if not existing:
        c.execute('''
            INSERT INTO signals (
                timestamp, symbol, display_name, category, action,
                entry_price, stop_loss, tp1, tp2, confidence, ai_analysis, tech_reasons, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
        ''', (
            data['timestamp'], data['symbol'], data['display_name'], data['category'],
            data['action'], data['entry_price'], data['stop_loss'], data['tp1'],
            data['tp2'], data['confidence'], data['ai_analysis'],
            json.dumps(data['tech_reasons'], ensure_ascii=False)
        ))
        conn.commit()
    conn.close()

def update_active_signals_status(current_prices: dict):
    """
    يتحقق مما إذا كانت التوصيات النشطة قد ضربت الهدف (TP) أو وقف الخسارة (SL).
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, symbol, action, stop_loss, tp1, tp2 FROM signals WHERE status = 'ACTIVE'")
    rows = c.fetchall()
    for row in rows:
        sig_id, sym, action, sl, tp1, tp2 = row
        if sym in current_prices:
            price = current_prices[sym]
            if action == "BUY":
                if price >= tp2:
                    c.execute("UPDATE signals SET status = 'HIT TP2 ✅' WHERE id = ?", (sig_id,))
                elif price >= tp1:
                    c.execute("UPDATE signals SET status = 'HIT TP1 🎯' WHERE id = ?", (sig_id,))
                elif price <= sl:
                    c.execute("UPDATE signals SET status = 'HIT SL ❌' WHERE id = ?", (sig_id,))
            elif action == "SELL":
                if price <= tp2:
                    c.execute("UPDATE signals SET status = 'HIT TP2 ✅' WHERE id = ?", (sig_id,))
                elif price <= tp1:
                    c.execute("UPDATE signals SET status = 'HIT TP1 🎯' WHERE id = ?", (sig_id,))
                elif price >= sl:
                    c.execute("UPDATE signals SET status = 'HIT SL ❌' WHERE id = ?", (sig_id,))
    conn.commit()
    conn.close()

def get_recent_signals(limit=50):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    for r in rows:
        try:
            r['tech_reasons'] = json.loads(r['tech_reasons'])
        except:
            r['tech_reasons'] = []
    conn.close()
    return rows

def log_event(msg: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    c.execute("INSERT INTO system_logs (timestamp, message) VALUES (?, ?)", (now, msg))
    c.execute("DELETE FROM system_logs WHERE id NOT IN (SELECT id FROM system_logs ORDER BY id DESC LIMIT 30)")
    conn.commit()
    conn.close()
