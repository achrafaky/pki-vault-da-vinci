import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "pki_vault.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cn TEXT NOT NULL,
            serial TEXT UNIQUE,
            san TEXT DEFAULT '',
            type_cert TEXT DEFAULT 'server',
            key_algo TEXT DEFAULT 'rsa',
            key_size INTEGER DEFAULT 2048,
            status TEXT DEFAULT 'valid',
            cert_path TEXT,
            sign_ms REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            revoked_at DATETIME,
            rev_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target TEXT,
            ip TEXT,
            details TEXT,
            severity TEXT DEFAULT 'info',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        db.commit()

def log_action(action, target=None, ip=None, details=None, severity='info'):
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_logs (action,target,ip,details,severity) VALUES (?,?,?,?,?)",
            (action, target, ip, details, severity)
        )
        db.commit()

def get_stats():
    with get_db() as db:
        total   = db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
        valid   = db.execute("SELECT COUNT(*) FROM certificates WHERE status='valid'").fetchone()[0]
        revoked = db.execute("SELECT COUNT(*) FROM certificates WHERE status='revoked'").fetchone()[0]
        expired = db.execute("SELECT COUNT(*) FROM certificates WHERE status='expired'").fetchone()[0]
        ms_row  = db.execute("SELECT AVG(sign_ms) FROM certificates WHERE sign_ms IS NOT NULL").fetchone()[0]
        logs    = db.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 20").fetchall()
    health = max(0, int(100 - (revoked + expired) / max(total, 1) * 50))
    return {
        'total': total, 'valid': valid, 'revoked': revoked,
        'expired': expired, 'health': health,
        'avg_sign_ms': round(ms_row or 0, 1),
        'logs': [dict(l) for l in logs]
    }

def get_chart_data():
    with get_db() as db:
        rows = db.execute("""
            SELECT date(created_at) as day, COUNT(*) as cnt
            FROM certificates
            WHERE created_at >= date('now','-30 days')
            GROUP BY day ORDER BY day
        """).fetchall()
    base = {}
    for i in range(30):
        d = (date.today() - timedelta(days=29-i)).isoformat()
        base[d] = 0
    for r in rows:
        base[r['day']] = r['cnt']
    return list(base.keys()), list(base.values())

# Fonctions pour les widgets avancés
def get_advanced_stats():
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
        expiring = db.execute(
            "SELECT COUNT(*) FROM certificates WHERE date(expires_at) BETWEEN date('now') AND date('now','+7 days') AND status='valid'"
        ).fetchone()[0]
        revoked = db.execute("SELECT COUNT(*) FROM certificates WHERE status='revoked'").fetchone()[0]
        hsm_load = min(100, int(total * 2.5))
        return {'total': total, 'expiring_soon': expiring, 'revoked': revoked, 'hsm_load': hsm_load}

def get_algo_health():
    with get_db() as db:
        rsa = db.execute("SELECT COUNT(*) FROM certificates WHERE key_algo='rsa'").fetchone()[0]
        ecdsa = db.execute("SELECT COUNT(*) FROM certificates WHERE key_algo='ecdsa'").fetchone()[0]
        total = rsa + ecdsa
        pq = max(0, int(total * 0.1))
        return {'rsa': rsa, 'ecdsa': ecdsa, 'pq': pq}

def get_timeline():
    with get_db() as db:
        rows = db.execute("SELECT cn, expires_at, type_cert FROM certificates ORDER BY expires_at").fetchall()
        return [dict(r) for r in rows]

def get_impact(ca_type):
    with get_db() as db:
        impacted = db.execute("SELECT COUNT(*) FROM certificates WHERE type_cert='leaf' AND status='valid'").fetchone()[0]
    return impacted
