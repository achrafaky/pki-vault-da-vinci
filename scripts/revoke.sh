#!/usr/bin/env bash
set -euo pipefail
RED='\033[0;31m';GRN='\033[0;32m';CYN='\033[0;36m';NC='\033[0m'
ok(){ echo -e "${GRN}[✔]${NC} $*"; }
err(){ echo -e "${RED}[✘]${NC} $*"; exit 1; }

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RD="$(cd "$SD/.." && pwd)"
source "$RD/.env"
INTER_PASS="${INTER_PASS:?}"

CERT="${1:?Usage: revoke.sh <cert_path> [raison]}"
REASON="${2:-keyCompromise}"
[[ -f "$CERT" ]] || err "Certificat introuvable: $CERT"

echo -e "\n${CYN}Révocation : $CERT (raison: $REASON)${NC}"
(cd "$RD" && openssl ca -config "config/inter.cnf" \
    -revoke "$CERT" -crl_reason "$REASON" -passin "pass:$INTER_PASS")
ok "Révoqué dans index.txt"

(cd "$RD" && openssl ca -config "config/inter.cnf" -gencrl \
    -passin "pass:$INTER_PASS" -out "pki/intermediate/crl/inter.crl.pem")
ok "CRL mise à jour"

R=$((cd "$RD" && openssl verify \
    -CAfile "pki/intermediate/certs/chain.crt.pem" \
    -CRLfile "pki/intermediate/crl/inter.crl.pem" \
    -crl_check "$CERT") 2>&1 || true)
echo "$R" | grep -q "revoked" && ok "✅ Cert bien RÉVOQUÉ dans la CRL"
echo "[$(date '+%F %T')] REVOKE $CERT $REASON" >> "$RD/logs/pki.log"
