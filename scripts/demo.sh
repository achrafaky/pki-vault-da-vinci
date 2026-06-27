#!/usr/bin/env bash
set -euo pipefail
RED='\033[0;31m';GRN='\033[0;32m';CYN='\033[0;36m';BOLD='\033[1m';NC='\033[0m'
ok(){ echo -e "${GRN}[✔]${NC} $*"; }
step(){ echo -e "\n${BOLD}${CYN}╔══ $* ══╗${NC}"; }

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RD="$(cd "$SD/.." && pwd)"
T0=$(date +%s)
source "$RD/.env"

clear
echo -e "${CYN}${BOLD}  PKI-VAULT DA VINCI — DÉMONSTRATION COMPLÈTE${NC}\n"
sleep 1

step "1/6 · Initialisation PKI"
bash "$SD/init_ca.sh"; ok "PKI initialisée"

step "2/6 · Certificat RSA — api.demo.local"
bash "$SD/gen_csr.sh" "api.demo.local" "www.api.demo.local" rsa 2048
bash "$SD/sign_cert.sh" "api.demo.local" server 365
ok "api.demo.local (RSA 2048)"

step "3/6 · Certificat ECDSA — store.demo.local"
bash "$SD/gen_csr.sh" "store.demo.local" "" ecdsa 384
bash "$SD/sign_cert.sh" "store.demo.local" server 365
ok "store.demo.local (ECDSA P-384)"

step "4/6 · Vérification chaînes"
bash "$SD/verify.sh" "$RD/pki/leaf/certs/api_demo_local.crt.pem"

step "5/6 · Révocation api.demo.local"
(cd "$RD" && openssl ca -config config/inter.cnf \
    -revoke pki/leaf/certs/api_demo_local.crt.pem \
    -crl_reason keyCompromise -passin "pass:$INTER_PASS")
(cd "$RD" && openssl ca -config config/inter.cnf -gencrl \
    -passin "pass:$INTER_PASS" -out pki/intermediate/crl/inter.crl.pem)
ok "Révoqué + CRL mise à jour"

step "6/6 · Vérification post-révocation"
R=$((cd "$RD" && openssl verify \
    -CAfile pki/intermediate/certs/chain.crt.pem \
    -CRLfile pki/intermediate/crl/inter.crl.pem \
    -crl_check pki/leaf/certs/api_demo_local.crt.pem) 2>&1 || true)
echo "$R" | grep -q "revoked" && ok "api.demo.local → ❌ RÉVOQUÉ (correct)"
(cd "$RD" && openssl verify -CAfile pki/intermediate/certs/chain.crt.pem \
    pki/leaf/certs/store_demo_local.crt.pem) && ok "store.demo.local → ✅ VALIDE"

T1=$(date +%s)
echo -e "\n${BOLD}${GRN}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GRN}║  🏆  DÉMO TERMINÉE en $((T1-T0)) secondes  ║${NC}"
echo -e "${BOLD}${GRN}╚══════════════════════════════════════╝${NC}"
echo -e "\n${CYN}Lancer : python3 run.py${NC}"
echo -e "${CYN}Firefox : http://localhost:5000${NC}\n"
