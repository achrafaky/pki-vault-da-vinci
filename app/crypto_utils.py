import time, subprocess
from pathlib import Path
from datetime import timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
import ipaddress

BASE_DIR = Path(__file__).parent.parent
PKI_DIR  = BASE_DIR / "pki"
CFG_DIR  = BASE_DIR / "config"

def load_env():
    env = {}
    ef = BASE_DIR / ".env"
    if ef.exists():
        for line in ef.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def run_ssl(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           cwd=str(cwd or BASE_DIR), timeout=30)
        return r.returncode == 0, r.stdout, r.stderr
    except Exception as e:
        return False, '', str(e)

def generate_key(algo, size):
    if algo == 'ecdsa':
        curves = {256: ec.SECP256R1(), 384: ec.SECP384R1()}
        key = ec.generate_private_key(curves.get(size, ec.SECP384R1()), default_backend())
    else:
        key = rsa.generate_private_key(65537, size, default_backend())
    return key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())

def build_csr(key_pem, cn, org, country, san_list):
    key = serialization.load_pem_private_key(key_pem, None, default_backend())
    san_objs = []
    for s in san_list:
        s = s.strip()
        if not s: continue
        try: san_objs.append(x509.IPAddress(ipaddress.ip_address(s)))
        except ValueError: san_objs.append(x509.DNSName(s))
    builder = (x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country[:2].upper()),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]))
        .add_extension(x509.SubjectAlternativeName(san_objs or [x509.DNSName(cn)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True))
    csr = builder.sign(key, hashes.SHA256(), default_backend())
    return csr.public_bytes(serialization.Encoding.PEM)

def parse_cert(path):
    try:
        cert = x509.load_pem_x509_certificate(Path(path).read_bytes(), default_backend())
        sans = []
        try:
            ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            for n in ext.value:
                sans.append(f"DNS:{n.value}" if isinstance(n, x509.DNSName) else f"IP:{n.value}")
        except x509.ExtensionNotFound: pass
        def _cn(name):
            a = name.get_attributes_for_oid(NameOID.COMMON_NAME)
            return a[0].value if a else 'Unknown'
        nb = cert.not_valid_before_utc if hasattr(cert,'not_valid_before_utc') \
             else cert.not_valid_before.replace(tzinfo=timezone.utc)
        na = cert.not_valid_after_utc  if hasattr(cert,'not_valid_after_utc') \
             else cert.not_valid_after.replace(tzinfo=timezone.utc)
        key = cert.public_key()
        key_info = f"RSA {key.key_size}" if isinstance(key, rsa.RSAPublicKey) else f"ECDSA {key.curve.name}"
        return {'cn':_cn(cert.subject),'serial':hex(cert.serial_number)[2:].upper(),
                'san':', '.join(sans),'issuer':_cn(cert.issuer),
                'not_before':nb,'not_after':na,'key_info':key_info}
    except Exception as e:
        return {'error': str(e)}

def sign_csr(csr_path, cn, cert_type, days, inter_pass):
    safe = cn.replace('.','_').replace('*','W').replace(' ','_')
    out  = PKI_DIR / "leaf/certs" / f"{safe}.crt.pem"
    t0 = time.perf_counter()
    ok, stdout, stderr = run_ssl(['openssl','ca','-config',str(CFG_DIR/'inter.cnf'),
        '-extensions',f"{cert_type}_cert",'-days',str(days),
        '-notext','-md','sha256','-passin',f'pass:{inter_pass}',
        '-batch','-in',str(csr_path),'-out',str(out)])
    ms = (time.perf_counter()-t0)*1000
    if not ok: raise RuntimeError(f"OpenSSL error: {stderr}")
    out.chmod(0o444)
    ok2,serial_out,_ = run_ssl(['openssl','x509','-in',str(out),'-noout','-serial'])
    serial = serial_out.strip().split('=')[1] if ok2 and '=' in serial_out else 'UNKNOWN'
    return out, round(ms,1), serial

def revoke_cert(cert_path, reason, inter_pass):
    ok,_,err = run_ssl(['openssl','ca','-config',str(CFG_DIR/'inter.cnf'),
        '-revoke',str(cert_path),'-crl_reason',reason,'-passin',f'pass:{inter_pass}'])
    if not ok: raise RuntimeError(f"Revoke failed: {err}")
    run_ssl(['openssl','ca','-config',str(CFG_DIR/'inter.cnf'),'-gencrl',
        '-passin',f'pass:{inter_pass}','-out',str(PKI_DIR/'intermediate/crl/inter.crl.pem')])

def verify_cert(cert_path):
    chain = PKI_DIR/"intermediate/certs/chain.crt.pem"
    crl   = PKI_DIR/"intermediate/crl/inter.crl.pem"
    checks = {}
    ok,_,_ = run_ssl(['openssl','x509','-in',str(cert_path),'-noout'])
    checks['format'] = ok
    ok,_,_ = run_ssl(['openssl','x509','-in',str(cert_path),'-noout','-checkend','0'])
    checks['dates'] = ok
    if chain.exists():
        ok,_,_ = run_ssl(['openssl','verify','-CAfile',str(chain),str(cert_path)])
        checks['chain'] = ok
    else: checks['chain'] = None
    if crl.exists() and chain.exists():
        ok,out,err = run_ssl(['openssl','verify','-CAfile',str(chain),
            '-CRLfile',str(crl),'-crl_check',str(cert_path)])
        checks['crl'] = ok
        checks['revoked'] = 'revoked' in (out+err).lower()
    else: checks['crl']=None; checks['revoked']=False
    ok2,text,_ = run_ssl(['openssl','x509','-in',str(cert_path),'-noout','-text'])
    checks['no_sha1'] = 'sha1WithRSA' not in (text or '').lower()
    total = sum(1 for v in checks.values() if v is not None)
    score = sum(1 for v in checks.values() if v is True)
    checks['score']=score; checks['total']=total
    checks['pct']=int(score*100/total) if total else 0
    return checks
