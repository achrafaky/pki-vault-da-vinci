#!/usr/bin/env bash
set -euo pipefail
RED='\033[0;31m';GRN='\033[0;32m';YLW='\033[1;33m';BLU='\033[0;34m';BOLD='\033[1m';NC='\033[0m'
ok()  { echo -e "${GRN}  ✔ $*${NC}"; ((SCORE++)); }
fail(){ echo -e "${RED}  ✘ $*${NC}"; }

CERT="${1:?Usage: verify.sh <cert>}"
[[ -f "$CERT" ]] || { echo -e "${RED}Introuvable: $CERT${NC}"; exit 1; }

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RD="$(cd "$SD/.." && pwd)"
CHAIN="$RD/pki/intermediate/certs/chain.crt.pem"
CRL="$RD/pki/intermediate/crl/inter.crl.pem"
SCORE=0; MAX=5

echo -e "\n${BOLD}━━ Vérification : $(basename $CERT) ━━${NC}\n"

# 1. Format X.509
if openssl x509 -in "$CERT" -noout 2>/dev/null; then
    ok "Format X.509 valide"
else
    fail "Format invalide"
    exit 1
fi

# 2. Dates de validité
if openssl x509 -in "$CERT" -noout -checkend 0 2>/dev/null; then
    ok "Dates valides"
else
    fail "EXPIRÉ"
fi

# 3. Chaîne de confiance
if [[ -f "$CHAIN" ]]; then
    if (cd "$RD" && openssl verify -CAfile "$CHAIN" "$CERT" &>/dev/null); then
        ok "Chaîne Root→Inter→Leaf valide"
    else
        fail "Chaîne invalide"
    fi
fi

# 4. CRL (non révoqué)
if [[ -f "$CRL" ]]; then
    R=$((cd "$RD" && openssl verify -CAfile "$CHAIN" -CRLfile "$CRL" -crl_check "$CERT") 2>&1 || true)
    if echo "$R" | grep -q "revoked"; then
        fail "RÉVOQUÉ dans la CRL"
    else
        ok "Non révoqué (CRL vérifiée)"
    fi
fi

# 5. Algorithme (SHA-256+)
TEXT=$(openssl x509 -in "$CERT" -noout -text 2>/dev/null)
if echo "$TEXT" | grep -qi "sha1WithRSA"; then
    fail "SHA-1 obsolète"
else
    ok "Algorithme moderne (SHA-256+)"
fi

PCT=$(( SCORE * 100 / MAX ))
echo ""
if [[ $SCORE -eq $MAX ]]; then
    echo -e "${BOLD}${GRN}Score : $SCORE/$MAX (${PCT}%) ✅ PARFAIT${NC}"
elif [[ $SCORE -ge 3 ]]; then
    echo -e "${BOLD}${YLW}Score : $SCORE/$MAX (${PCT}%) ⚠ ATTENTION${NC}"
else
    echo -e "${BOLD}${RED}Score : $SCORE/$MAX (${PCT}%) ❌ INVALIDE${NC}"
fi
