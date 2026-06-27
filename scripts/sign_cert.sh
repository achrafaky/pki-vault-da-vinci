#!/usr/bin/env bash
set -euo pipefail
RED='\033[0;31m';GRN='\033[0;32m';CYN='\033[0;36m';BOLD='\033[1m';NC='\033[0m'
ok(){ echo -e "${GRN}[✔]${NC} $*"; }
err(){ echo -e "${RED}[✘]${NC} $*"; exit 1; }

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RD="$(cd "$SD/.." && pwd)"
source "$RD/.env"
INTER_PASS="${INTER_PASS:?}"

CN="${1:?Usage: sign_cert.sh <CN> [server|client] [jours]}"
TYPE="${2:-server}"; DAYS="${3:-365}"
SAFE=$(echo "$CN" | tr '.' '_' | tr '*' 'W' | tr -cd '[:alnum:]_-')

CSR="$RD/pki/leaf/csr/${SAFE}.csr.pem"
CRT="$RD/pki/leaf/certs/${SAFE}.crt.pem"
[[ -f "$CSR" ]] || err "CSR introuvable: $CSR"

SIGALGO=$(openssl req -in "$CSR" -noout -text 2>/dev/null | grep "Signature Algorithm" | head -1)
echo "$SIGALGO" | grep -qi sha1 && err "SHA-1 refusé !"

echo -e "\n${BOLD}${CYN}━━ Signature : $CN ($TYPE · $DAYS jours) ━━${NC}"

T0=$(date +%s%N)
(cd "$RD" && openssl ca -config "config/inter.cnf" \
    -extensions "${TYPE}_cert" -days "$DAYS" \
    -notext -md sha256 -passin "pass:$INTER_PASS" -batch \
    -in "$CSR" -out "$CRT")
chmod 444 "$CRT"
MS=$(( ($(date +%s%N) - T0) / 1000000 ))

SERIAL=$(openssl x509 -in "$CRT" -noout -serial | cut -d= -f2)
(cd "$RD" && openssl verify -CAfile "pki/intermediate/certs/chain.crt.pem" "$CRT") \
    && ok "Chaîne ✔ (signé en ${MS}ms)"

echo "[$(date '+%F %T')] SIGN $CN $TYPE $SERIAL ${MS}ms" >> "$RD/logs/pki.log"
echo -e "${GRN}Cert   : $CRT\nSerial : $SERIAL\nTemps  : ${MS}ms${NC}"
