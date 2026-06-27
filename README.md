# 🏛️ PKI VAULT DA VINCI

## Infrastructure à Clés Publiques (PKI) à Trois Niveaux

> *"La sécurité numérique commence par une confiance bien construite."*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-black?logo=flask)](https://flask.palletsprojects.com/)
[![OpenSSL](https://img.shields.io/badge/OpenSSL-3.0+-red?logo=openssl)](https://www.openssl.org/)
[![Three.js](https://img.shields.io/badge/Three.js-3D-black?logo=three.js)](https://threejs.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.2-purple?logo=bootstrap)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🎯 À propos

Ce projet est une **Infrastructure à Clés Publiques (PKI) à trois niveaux** conforme aux normes **X.509**.

### Objectifs pédagogiques
- 🔐 Comprendre la hiérarchie et la chaîne de confiance
- 🏛️ Générer, signer et distribuer des certificats numériques
- 🛡️ Gérer la sécurité des clés privées
- 📜 Implémenter la gestion des CSR et CRL
- 🖥️ Proposer une interface web Flask
- ✅ Vérifier la validité et la chaîne de confiance

---

## 🏗️ Architecture

\`\`\`
┌─────────────────────────────────────────────────────────┐
│              ROOT CA (RSA 4096 · 20 ans)               │
│           Autorité Racine – Auto-signée                │
│              Hors ligne (Air-Gapped)                   │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ ✦ Signe
                          ▼
┌─────────────────────────────────────────────────────────┐
│         INTERMEDIATE CA (RSA 4096 · 10 ans)            │
│       Autorité Intermédiaire – Signe les Leaf          │
│                    En ligne                            │
└────────────┬────────────────────┬──────────────────────┘
             │                    │
     ✦ Signe │                    │ ✦ Signe
             ▼                    ▼
┌──────────────────┐  ┌──────────────────┐
│   LEAF SERVER    │  │   LEAF CLIENT    │
│   RSA 2048       │  │   ECDSA P-384    │
│   1 an           │  │   1 an           │
└──────────────────┘  └──────────────────┘
\`\`\`

---

## ✨ Fonctionnalités

| Fonctionnalité | Statut |
|:---------------|:-------|
| Génération RSA/ECDSA | ✅ |
| CSR avec SAN | ✅ |
| Signature par CA | ✅ |
| Vérification 5/5 | ✅ |
| Révocation et CRL | ✅ |
| Dashboard Flask | ✅ |
| Vue 3D interactive | ✅ |
| Console d'audit | ✅ |

---

## 🛠️ Technologies

| Technologie | Version |
|:------------|:--------|
| Python | 3.10+ |
| Flask | 3.0.0 |
| OpenSSL | 3.0+ |
| cryptography | 42.0.0 |
| Three.js | r128 |
| Chart.js | 4.4.0 |
| Bootstrap | 5.3.2 |
| SQLite | 3.x |

---

## 🚀 Installation

\`\`\`bash
# Prérequis
sudo apt update
sudo apt install -y openssl python3 python3-pip python3-venv git tree

# Cloner
git clone https://github.com/achrafaky/pki-vault-da-vinci.git
cd pki-vault-da-vinci

# Environnement virtuel
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialiser la PKI
bash scripts/init_ca.sh

# Lancer l'application
python3 run.py
\`\`\`

🌐 **Dashboard :** [http://localhost:5000](http://localhost:5000)

---

## 📖 Commandes

| Commande | Description |
|:---------|:------------|
| `bash scripts/gen_csr.sh <CN> [SAN] [rsa\|ecdsa] [taille]` | Générer une CSR |
| `bash scripts/sign_cert.sh <CN> [server\|client] [jours]` | Signer |
| `bash scripts/verify.sh <cert>` | Vérifier |
| `bash scripts/revoke.sh <cert> [raison]` | Révoquer |

---

## 📸 Captures d'écran

| Capture | Description |
|:--------|:------------|
| `images/13_dashboard.png` | Dashboard principal |
| `images/21_viz_3d.png` | Vue 3D interactive |
| `images/09_verify_5_5.png` | Score 5/5 |
| `images/11_verify_4_5.png` | Score 4/5 après révocation |

---

## 📊 Justifications (NIST SP 800-57)

| Composant | Algorithme | Taille | Sécurité |
|:----------|:-----------|:-------|:---------|
| Root CA | RSA | 4096 bits | 128 bits |
| Intermediate CA | RSA | 4096 bits | 128 bits |
| Leaf Server | RSA | 2048 bits | 112 bits |
| Leaf Client | ECDSA | P-384 | 192 bits |

**Durées :** Root 20 ans · Intermediate 10 ans · Leaf 1 an

---

## 👤 Auteur

**Acharf Akiyaf** – Master MMSD, FST Tanger  
[GitHub](https://github.com/achrafaky)

---

## 👨‍🏫 Encadrement

Mr LECHHAB OUADRASSI Nihad – Professeur  
Mr AZMANI Abdellah – Supervision

---

## 📜 Licence

MIT – voir [LICENSE](LICENSE)

---

<p align="center">
  <b>✨ Made with ❤️ by Acharf Akiyaf ✨</b><br>
  <i>Master MMSD – Cryptographie & Blockchain – 2025</i>
</p>
