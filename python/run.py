#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
from app.app import app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    print(f"\n🔐 PKI-VAULT Da Vinci — http://localhost:{port}")
    print(f"   Vue 3D        — http://localhost:{port}/viz\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
