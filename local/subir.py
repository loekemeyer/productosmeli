#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sube el data.json que ya está en esta carpeta al repositorio.
Sirve para publicar los resultados sin volver a escanear Mercado Libre.
Da un mensaje claro si el token falla (401 = token inválido, 403 = falta permiso).
"""
import os
import json
import base64
import urllib.request
import urllib.error

GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
GH_REPO = os.environ.get("GH_REPO", "loekemeyer/productosmeli").strip()

if not GH_TOKEN:
    print("❌ No hay GH_TOKEN. Primero: set GH_TOKEN=tu_token")
    raise SystemExit(1)
if not os.path.exists("data.json"):
    print("❌ No encuentro data.json en esta carpeta. Corré primero radar_browser.py")
    raise SystemExit(1)

data = open("data.json", "rb").read()
try:
    n = len(json.loads(data).get("items", []))
    print(f"Subiendo data.json ({n} artículos) a {GH_REPO}…")
except Exception:
    print("Subiendo data.json…")

api = f"https://api.github.com/repos/{GH_REPO}/contents/data.json"
headers = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "radar-local",
}

sha = None
try:
    with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=30) as r:
        sha = json.loads(r.read()).get("sha")
except urllib.error.HTTPError as e:
    if e.code not in (404,):
        print(f"⚠️  Al leer el archivo actual: HTTP {e.code}")

payload = {"message": "Actualizar resultados (manual)",
           "content": base64.b64encode(data).decode()}
if sha:
    payload["sha"] = sha

try:
    req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                 method="PUT", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"✅ ¡SUBIDO! (HTTP {r.status})")
        print("   Mirá el panel en 1-2 min: https://loekemeyer.github.io/productosmeli/")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", "replace")[:300] if e.fp else ""
    print(f"❌ Falló la subida: HTTP {e.code}")
    print("   ", body)
    if e.code == 401:
        print("   → El token no es válido (viejo/revocado o mal pegado). Generá uno nuevo.")
    elif e.code == 403:
        print("   → Al token le falta el permiso 'Contents: Read and write' sobre el repo.")
    elif e.code == 404:
        print("   → Revisá que el repo sea correcto y que el token tenga acceso a él.")

if os.name == "nt":
    input("\nApretá Enter para cerrar…")
