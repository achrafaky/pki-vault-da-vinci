#!/usr/bin/env python3
import sqlite3
import re
from pathlib import Path

DB_PATH = Path("pki_vault.db")
INDEX_PATH = Path("pki/intermediate/db/index.txt")

if not INDEX_PATH.exists():
    print("❌ index.txt introuvable")
    exit(1)

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

# Créer la table si elle n'existe pas
cursor.execute("""
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
)
""")
conn.commit()

# Lire index.txt
with open(INDEX_PATH, "r") as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) < 6:
            continue
        status_flag = parts[0]  # V, R, E
        exp_date = parts[1]
        rev_date = parts[2] if parts[2] else None
        serial = parts[3]
        subject = parts[5]

        # Extraire CN
        cn_match = re.search(r'CN=([^,/]+)', subject)
        cn = cn_match.group(1) if cn_match else "unknown"

        # Déterminer le statut
        if status_flag == 'V':
            status = 'valid'
            revoked_at = None
            rev_reason = None
        elif status_flag == 'R':
            status = 'revoked'
            revoked_at = rev_date
            rev_reason = 'keyCompromise'
        else:
            status = 'expired'
            revoked_at = None
            rev_reason = None

        # Vérifier si le certificat existe déjà
        cursor.execute("SELECT id FROM certificates WHERE serial = ?", (serial,))
        if cursor.fetchone():
            continue

        # Chemin du certificat
        cert_path = Path(f"pki/leaf/certs/{cn.replace('.','_')}_local.crt.pem")
        if not cert_path.exists():
            cert_path = Path(f"pki/leaf/certs/{cn}.crt.pem")
            if not cert_path.exists():
                cert_path = None

        # Insérer
        cursor.execute("""
            INSERT INTO certificates (cn, serial, status, cert_path, expires_at, revoked_at, rev_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cn, serial, status, str(cert_path) if cert_path else None, exp_date, revoked_at, rev_reason))

conn.commit()
conn.close()
print("✅ Base de données synchronisée")
