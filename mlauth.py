#!/usr/bin/env python3
"""Utilidades de OAuth de Mercado Libre + persistencia del refresh token.

Mercado Libre usa OAuth 2.0. El access token dura ~6 h y el refresh token es
de un solo uso (rota en cada renovación), así que tras cada refresh hay que
GUARDAR el nuevo refresh token para la próxima corrida. En GitHub Actions eso
se hace actualizando el secreto del repositorio vía la API de GitHub (requiere
un PAT con permiso de escritura sobre Secrets).
"""

import json
import base64
import urllib.parse
import urllib.request

API = "https://api.mercadolibre.com"
GH = "https://api.github.com"


def _post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def exchange_code(client_id, client_secret, code, redirect_uri):
    """Canjea el 'code' de la autorización inicial por access + refresh token."""
    return _post_form(f"{API}/oauth/token", {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    })


def refresh(client_id, client_secret, refresh_token):
    """Renueva el access token. Devuelve dict con access_token y refresh_token nuevos."""
    return _post_form(f"{API}/oauth/token", {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    })


# --------------------------------------------------------------------------- #
# Guardar un secreto en el repo de GitHub (para persistir el refresh token)
# --------------------------------------------------------------------------- #
def _gh(url, pat, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {pat}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", "replace")
        return json.loads(raw) if raw else {}


def update_repo_secret(repo, pat, name, value):
    """Crea/actualiza un Actions secret del repositorio (repo = 'owner/name')."""
    from nacl import encoding, public  # PyNaCl: cifrado sellado exigido por GitHub
    pk = _gh(f"{GH}/repos/{repo}/actions/secrets/public-key", pat)
    sealed = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(sealed.encrypt(value.encode())).decode()
    _gh(f"{GH}/repos/{repo}/actions/secrets/{name}", pat, method="PUT",
        payload={"encrypted_value": enc, "key_id": pk["key_id"]})
