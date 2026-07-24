#!/usr/bin/env python3
"""Bootstrap OAuth: canjea el 'code' inicial por tokens y guarda el refresh
token como secreto del repo. Se ejecuta UNA sola vez desde el workflow
'setup-token'. No imprime tokens (el repo es público)."""

import os
import sys
import mlauth

CLIENT_ID = os.environ["ML_CLIENT_ID"].strip()
CLIENT_SECRET = os.environ["ML_CLIENT_SECRET"].strip()
CODE = os.environ["ML_CODE"].strip()
REDIRECT_URI = os.environ["ML_REDIRECT_URI"].strip()
GH_PAT = os.environ["GH_PAT"].strip()
REPO = os.environ["GITHUB_REPOSITORY"].strip()

print("Canjeando el código por tokens…")
tok = mlauth.exchange_code(CLIENT_ID, CLIENT_SECRET, CODE, REDIRECT_URI)
refresh = tok.get("refresh_token")
if not refresh:
    print("ERROR: la respuesta no trae refresh_token:", tok, file=sys.stderr)
    sys.exit(1)

mlauth.update_repo_secret(REPO, GH_PAT, "ML_REFRESH_TOKEN", refresh)
print("✅ Listo. ML_REFRESH_TOKEN guardado como secreto del repo.")
print("   Ya podés ejecutar el workflow 'Radar Importados (diario)'.")
