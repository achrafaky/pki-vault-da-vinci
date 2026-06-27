#!/usr/bin/env bash
set -euo pipefail
RED='\033[0;31m';GRN='\033[0;32m';CYN='\033[0;36m';BOLD='\033[1m';NC='\033[0m'
log(){ echo -e "${CYN}[•]${NC} $*"; }
ok(){ echo -e "${GRN}[✔]${NC} $*"; }
err(){ echo -e "${RED}[✘]${NC} $*"; exit 1; }
step(){ echo -e "\n${BOLD}${CYN}━━ $* ━━${NC}"; }

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RD="$(cd "$SD/.." && pwd)"
PKI="$RD/pki"; CFG="$RD/config"
mkdir -p "$RD/logs"

[[ -f "$RD/.env" ]] || err ".env introuvable"
source "$RD/.env"
ROOT_PASS="${ROOT_PASS:?}"; INTER_PASS="${INTER_PASS:?}"
ORG="${PKI_ORG:-PKI Vault Enterprise}"
CTR="${PKI_COUNTRY:-MA}"; ST="${PKI_STATE:-Tanger}"

step "1/5 — Bases de données"
for ca in root intermediate; do
    [[ -f "$PKI/$ca/db/index.txt" ]] || touch "$PKI/$ca/db/index.txt"
    [[ -f "$PKI/$ca/db/serial"    ]] || echo "01"   > "$PKI/$ca/db/serial"
    [[ -f "$PKI/$ca/db/crlnumber" ]] || echo "0100" > "$PKI/$ca/db/crlnumber"
done
chmod 700 "$PKI/root/private" "$PKI/intermediate/private" "$PKI/leaf/private"
ok "Bases de données initialisées"

step "2/5 — Root CA (RSA 4096 · 20 ans)"
RK="$PKI/root/private/root.key.pem"
RC="$PKI/root/certs/root.crt.pem"
if [[ ! -f "$RK" ]]; then
    log "Génération clé RSA 4096..."
    openssl genrsa -aes256 -passout "pass:$ROOT_PASS" -out "$RK" 4096
    chmod 400 "$RK"; ok "Clé Root générée (chmod 400)"
else echo "Clé Root déjà présente"; fi
if [[ ! -f "$RC" ]]; then
    openssl req -config "$CFG/root.cnf" -key "$RK" -passin "pass:$ROOT_PASS" \
        -new -x509 -days 7300 -sha256 -extensions v3_ca \
        -subj "/C=$CTR/ST=$ST/O=$ORG/CN=PKI Root CA" \
        -out "$RC"
    chmod 444 "$RC"; ok "Root CA auto-signée (20 ans)"
else echo "Root CA déjà présente"; fi

step "3/5 — Intermediate CA (RSA 4096 · 10 ans)"
IK="$PKI/intermediate/private/inter.key.pem"
IR="$PKI/intermediate/csr/inter.csr.pem"
IC="$PKI/intermediate/certs/inter.crt.pem"
CH="$PKI/intermediate/certs/chain.crt.pem"
if [[ ! -f "$IK" ]]; then
    openssl genrsa -aes256 -passout "pass:$INTER_PASS" -out "$IK" 4096
    chmod 400 "$IK"; ok "Clé Intermediate générée"
fi
if [[ ! -f "$IR" ]]; then
    openssl req -config "$CFG/inter.cnf" -key "$IK" -passin "pass:$INTER_PASS" \
        -new -sha256 \
        -subj "/C=$CTR/ST=$ST/O=$ORG/CN=PKI Intermediate CA" \
        -out "$IR"
    ok "CSR Intermediate créée"
fi
if [[ ! -f "$IC" ]]; then
    (cd "$RD" && openssl ca -config "$CFG/root.cnf" -extensions v3_intermediate_ca \
        -days 3650 -notext -md sha256 -passin "pass:$ROOT_PASS" -batch \
        -in "$IR" -out "$IC")
    chmod 444 "$IC"
    cat "$IC" "$RC" > "$CH"; chmod 444 "$CH"
    ok "Intermediate signée par Root + chaîne créée"
fi

step "4/5 — CRL initiales"
(cd "$RD" && openssl ca -config "$CFG/root.cnf" -gencrl \
    -passin "pass:$ROOT_PASS" -out "$PKI/root/crl/root.crl.pem")
(cd "$RD" && openssl ca -config "$CFG/inter.cnf" -gencrl \
    -passin "pass:$INTER_PASS" -out "$PKI/intermediate/crl/inter.crl.pem")
ok "CRL générées"

step "5/5 — Vérification chaîne"
(cd "$RD" && openssl verify -CAfile "$RC" "$IC") && ok "Root → Intermediate : ✔ VALIDE"

echo ""
echo -e "${BOLD}${GRN}╔════════════════════════════════╗${NC}"
echo -e "${BOLD}${GRN}║  ✅  PKI INITIALISÉE           ║${NC}"
echo -e "${BOLD}${GRN}╚════════════════════════════════╝${NC}"
echo "[$(date '+%F %T')] init_ca OK" >> "$RD/logs/pki.log"
