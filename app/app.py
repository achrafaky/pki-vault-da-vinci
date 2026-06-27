#!/usr/bin/env python3
import os, tempfile
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from app.models import init_db, get_db, log_action, get_stats, get_chart_data, get_advanced_stats, get_algo_health, get_timeline, get_impact
from app.crypto_utils import load_env, generate_key, build_csr, parse_cert, sign_csr, revoke_cert, verify_cert, PKI_DIR

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'pki-vault-2024')

with app.app_context():
    init_db()

@app.route('/')
def dashboard():
    stats = get_stats()
    labels, data = get_chart_data()
    root_ok  = (PKI_DIR/'root/certs/root.crt.pem').exists()
    inter_ok = (PKI_DIR/'intermediate/certs/inter.crt.pem').exists()
    donut = {'valid':stats['valid'],'revoked':stats['revoked'],'expired':stats['expired']}
    advanced = get_advanced_stats()
    algo = get_algo_health()
    timeline = get_timeline()
    return render_template('dashboard.html',
        stats=stats, chart_labels=labels, chart_data=data,
        donut=donut, root_ok=root_ok, inter_ok=inter_ok,
        advanced=advanced, algo=algo, timeline=timeline)

@app.route('/generate', methods=['GET','POST'])
def generate():
    if request.method == 'POST':
        cn=request.form.get('cn','').strip()
        san_raw=request.form.get('san','').strip()
        algo=request.form.get('algo','rsa')
        size=int(request.form.get('size',2048))
        org=request.form.get('org','PKI Vault Enterprise').strip()
        country=request.form.get('country','MA').strip()[:2].upper()
        if not cn: flash('Common Name obligatoire.','danger'); return redirect(url_for('generate'))
        try:
            safe=cn.replace('.','_').replace('*','W').replace(' ','_')
            key=generate_key(algo,size)
            kpath=PKI_DIR/'leaf/private'/f'{safe}.key.pem'
            kpath.write_bytes(key); kpath.chmod(0o600)
            sans=[s.strip() for s in san_raw.split(',') if s.strip()]
            if cn not in sans: sans=[cn]+sans
            csr=build_csr(key,cn,org,country,sans)
            cpath=PKI_DIR/'leaf/csr'/f'{safe}.csr.pem'; cpath.write_bytes(csr)
            log_action('GENERATE_CSR',cn,request.remote_addr,f"algo={algo} size={size}")
            flash(f'CSR générée pour {cn} ({algo.upper()} {size}).','success')
            return render_template('generate.html',generated=True,cn=cn,csr_content=csr.decode(),algo=algo,size=size)
        except Exception as e:
            flash(f'Erreur : {e}','danger')
    return render_template('generate.html',generated=False)

@app.route('/sign', methods=['GET','POST'])
def sign():
    if request.method == 'POST':
        ca_choice=request.form.get('ca','inter'); cert_type=request.form.get('type','server')
        days=int(request.form.get('days',365)); csr_file=request.files.get('csr_file')
        if not csr_file or not csr_file.filename: flash('Fichier CSR requis.','danger'); return redirect(url_for('sign'))
        env=load_env(); passw=env.get('ROOT_PASS' if ca_choice=='root' else 'INTER_PASS','')
        if not passw: flash('Mot de passe CA manquant.','danger'); return redirect(url_for('sign'))
        with tempfile.NamedTemporaryFile(suffix='.csr.pem',delete=False) as tmp:
            csr_file.save(tmp.name); tmp_path=Path(tmp.name)
        try:
            from cryptography import x509 as cx509
            from cryptography.hazmat.backends import default_backend as _db
            from cryptography.x509.oid import NameOID as _NOI
            csr_obj=cx509.load_pem_x509_csr(tmp_path.read_bytes(),_db())
            cns=csr_obj.subject.get_attributes_for_oid(_NOI.COMMON_NAME)
            cn=cns[0].value if cns else 'unknown'
            if 'sha1' in str(csr_obj.signature_hash_algorithm).lower():
                flash('SHA-1 refusé.','danger'); return redirect(url_for('sign'))
            out_crt,sign_ms,serial=sign_csr(tmp_path,cn,cert_type,days,passw)
            san_str=''
            try:
                ext=csr_obj.extensions.get_extension_for_class(cx509.SubjectAlternativeName)
                san_str=', '.join(f"DNS:{n.value}" if isinstance(n,cx509.DNSName) else f"IP:{n.value}" for n in ext.value)
            except: pass
            info=parse_cert(out_crt); exp=info.get('not_after')
            if exp and hasattr(exp,'replace'): exp=exp.replace(tzinfo=None)
            with get_db() as db:
                db.execute("INSERT INTO certificates (cn,serial,san,type_cert,key_algo,status,cert_path,sign_ms,expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (cn,serial,san_str,cert_type,'rsa','valid',str(out_crt),sign_ms,exp)); db.commit()
            log_action('SIGN_CERT',cn,request.remote_addr,f"serial={serial} ms={sign_ms:.0f}")
            flash(f'Signé : {cn} en {sign_ms:.0f}ms','success')
            return redirect(url_for('list_certs'))
        except Exception as e:
            flash(f'Erreur : {e}','danger'); return redirect(url_for('sign'))
        finally: tmp_path.unlink(missing_ok=True)
    return render_template('sign.html')

@app.route('/certificates')
def list_certs():
    filtre=request.args.get('status','all'); search=request.args.get('q','').strip()
    with get_db() as db:
        if search: rows=db.execute("SELECT * FROM certificates WHERE cn LIKE ? ORDER BY created_at DESC",(f'%{search}%',)).fetchall()
        elif filtre=='all': rows=db.execute("SELECT * FROM certificates ORDER BY created_at DESC").fetchall()
        else: rows=db.execute("SELECT * FROM certificates WHERE status=? ORDER BY created_at DESC",(filtre,)).fetchall()
    return render_template('list.html',certs=rows,filtre=filtre,search=search)

@app.route('/revoke/<int:cid>', methods=['POST'])
def revoke(cid):
    with get_db() as db: cert=db.execute("SELECT * FROM certificates WHERE id=?",(cid,)).fetchone()
    if not cert: flash('Introuvable.','danger'); return redirect(url_for('list_certs'))
    if cert['status']=='revoked': flash('Déjà révoqué.','warning'); return redirect(url_for('list_certs'))
    cp=cert['cert_path']
    if not cp or not Path(cp).exists(): flash('Fichier absent.','danger'); return redirect(url_for('list_certs'))
    reason=request.form.get('reason','keyCompromise'); env=load_env(); pw=env.get('INTER_PASS','')
    try:
        revoke_cert(Path(cp),reason,pw)
        with get_db() as db:
            db.execute("UPDATE certificates SET status='revoked',revoked_at=?,rev_reason=? WHERE id=?",(datetime.utcnow(),reason,cid)); db.commit()
        log_action('REVOKE',cert['cn'],request.remote_addr,f"reason={reason}",'warn')
        flash(f'{cert["cn"]} révoqué ({reason}).','success')
    except Exception as e: flash(f'Erreur : {e}','danger')
    return redirect(url_for('list_certs'))

@app.route('/verify', methods=['GET','POST'])
def verify():
    result=None
    if request.method=='POST':
        f=request.files.get('cert_file')
        if not f: flash('Fichier requis.','danger'); return redirect(url_for('verify'))
        with tempfile.NamedTemporaryFile(suffix='.pem',delete=False) as tmp:
            f.save(tmp.name); tp=Path(tmp.name)
        try:
            checks=verify_cert(tp); cert_info=parse_cert(tp)
            result={**checks,'cert_info':cert_info}
            log_action('VERIFY',cert_info.get('cn','?'),request.remote_addr,f"score={checks['score']}/{checks['total']}")
        finally: tp.unlink(missing_ok=True)
    return render_template('verify.html',result=result)

@app.route('/viz')
def viz():
    return render_template('viz.html')

# === WIDGETS AVANCÉS ===
@app.route('/api/advanced-stats')
def api_advanced_stats():
    return jsonify(get_advanced_stats())

@app.route('/api/algo-health')
def api_algo_health():
    return jsonify(get_algo_health())

@app.route('/api/timeline')
def api_timeline():
    return jsonify(get_timeline())

@app.route('/api/impact/<ca_type>')
def api_impact(ca_type):
    impacted = get_impact(ca_type)
    return jsonify({'impacted': impacted, 'ca_type': ca_type})

@app.route('/api/root-status')
def root_status():
    state_file = Path('.root-state')
    state = 'offline'
    if state_file.exists() and state_file.read_text().strip() == 'online':
        state = 'online'
    return jsonify({'status': state})

@app.route('/kill/<ca_type>', methods=['POST'])
def kill_switch(ca_type):
    if ca_type == 'inter':
        with get_db() as db:
            certs = db.execute("SELECT cert_path FROM certificates WHERE type_cert='leaf' AND status='valid'").fetchall()
            for row in certs:
                try:
                    revoke_cert(Path(row['cert_path']), 'keyCompromise', load_env().get('INTER_PASS',''))
                except: pass
            db.execute("UPDATE certificates SET status='revoked', revoked_at=? WHERE type_cert='leaf' AND status='valid'", (datetime.utcnow(),))
            db.commit()
        flash('Tous les certificats Leaf ont été révoqués (Kill Switch).', 'danger')
    elif ca_type == 'root':
        flash('Action non autorisée sur la Root CA (air-gapped).', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/api/graph-data')
def graph_data():
    root_ok=(PKI_DIR/'root/certs/root.crt.pem').exists()
    inter_ok=(PKI_DIR/'intermediate/certs/inter.crt.pem').exists()
    nodes=[
        {'id':'root','type':'root','label':'Root CA','algo':'RSA 4096','status':'active' if root_ok else 'missing'},
        {'id':'inter','type':'inter','label':'Intermediate CA','algo':'RSA 4096','status':'active' if inter_ok else 'missing'},
    ]
    edges=[]
    if root_ok and inter_ok: edges.append({'from':'root','to':'inter'})
    with get_db() as db: certs=db.execute("SELECT * FROM certificates ORDER BY created_at DESC").fetchall()
    for c in certs:
        nid=f"leaf_{c['id']}"
        nodes.append({'id':nid,'type':'leaf','label':c['cn'],'serial':c['serial'] or '',
            'status':c['status'],'algo':f"{c['key_algo'].upper()} {c['key_size']}",
            'expires':str(c['expires_at'] or '—'),'cert_id':c['id']})
        if inter_ok: edges.append({'from':'inter','to':nid})
    return jsonify({'nodes':nodes,'edges':edges})

@app.route('/api/stats')
def api_stats(): return jsonify(get_stats())

@app.route('/api/logs')
def api_logs():
    with get_db() as db: logs=db.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 5").fetchall()
    return jsonify([dict(l) for l in logs])

@app.route('/download/crl')
def dl_crl():
    p=PKI_DIR/'intermediate/crl/inter.crl.pem'
    if not p.exists(): flash('CRL non disponible.','warning'); return redirect(url_for('dashboard'))
    return send_file(str(p),as_attachment=True,download_name='inter.crl.pem')

@app.route('/download/chain')
def dl_chain():
    p=PKI_DIR/'intermediate/certs/chain.crt.pem'
    if not p.exists(): flash('Chaîne non disponible.','warning'); return redirect(url_for('dashboard'))
    return send_file(str(p),as_attachment=True,download_name='chain.crt.pem')
