#!/usr/bin/env bash
set -euo pipefail
RED='\033[0;31m';GRN='\033[0;32m';CYN='\033[0;36m';BOLD='\033[1m';NC='\033[0m'
ok(){ echo -e "${GRN}[✔]${NC} $*"; }
err(){ echo -e "${RED}[✘]${NC} $*"; exit 1; }

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RD="$(cd "$SD/.." && pwd)"
source "$RD/.env"

CN="${1:?Usage: gen_csr.sh <CN> [SANs] [rsa|ecdsa] [taille]}"
SANS="${2:-}"; ALGO="${3:-rsa}"; SIZE="${4:-2048}"
SAFE=$(echo "$CN" | tr '.' '_' | tr '*' 'W' | tr -cd '[:alnum:]_-')

echo -e "\n${BOLD}${CYN}━━ Génération : $CN ($ALGO $SIZE) ━━${NC}"

KF="$RD/pki/leaf/private/${SAFE}.key.pem"
if [[ "$ALGO" == "ecdsa" ]]; then
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-${SIZE} -out "$KF" 2>/dev/null \
        || openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-384 -out "$KF"
    ok "Clé ECDSA P-${SIZE} générée"
else
    openssl genrsa -out "$KF" "$SIZE"
    ok "Clé RSA ${SIZE} bits générée"
fi
chmod 600 "$KF"

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
cat > "$TMP" << CONF
[req]
default_bits=$SIZE
distinguished_name=dn
req_extensions=ext
prompt=no
[dn]
C=${PKI_COUNTRY:-MA}
ST=${PKI_STATE:-Tanger}
O=${PKI_ORG:-PKI Vault Enterprise}
CN=$CN
[ext]
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt
[alt]
DNS.1=$CN
CONF
IDX=2
if [[ -n "$SANS" ]]; then
    IFS=',' read -ra L <<< "$SANS"
    for s in "${L[@]}"; do
        s=$(echo "$s" | xargs)
        if [[ "$s" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "IP.$IDX=$s" >> "$TMP"
        else
            echo "DNS.$IDX=$s" >> "$TMP"
        fi
        ((IDX++))
    done
fi

CF="$RD/pki/leaf/csr/${SAFE}.csr.pem"
openssl req -config "$TMP" -key "$KF" -new -sha256 -out "$CF"
ok "CSR créée : $CF"
echo "[$(date '+%F %T')] GEN_CSR $CN $ALGO" >> "$RD/logs/pki.log"
echo -e "${GRN}Clé : $KF\nCSR : $CF${NC}"
