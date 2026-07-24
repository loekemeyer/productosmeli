#!/usr/bin/env python3
"""
Radar Importados — agente diario para Mercado Libre Argentina (MLA).

Reúne artículos de bazar/cocina que solo se consiguen con ENVÍO INTERNACIONAL
(productos importados / Cross-Border Trade) usando la API oficial de ML, y
genera `data.json` para el panel `index.html`.

Acceso: API oficial vía OAuth. En cada corrida:
  1) renueva el access token con el refresh token,
  2) guarda el nuevo refresh token (rota) como secreto del repo,
  3) busca con el filtro de origen de envío internacional,
  4) escribe data.json.

Variables de entorno (secretos del repo en GitHub Actions):
  ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REFRESH_TOKEN  -> OAuth de Mercado Libre
  GH_PAT               -> token de GitHub con permiso de escritura sobre Secrets
  GITHUB_REPOSITORY    -> 'owner/repo' (lo provee Actions automáticamente)

Si faltan credenciales, escribe un data.json de estado "esperando configuración"
y termina sin error (para no romper el panel).
"""

import os
import sys
import json
import time
import datetime
import urllib.parse
import urllib.request

import mlauth

SITE = "MLA"
INTL_ORIGIN_ID = "10215069"          # filtro ML: origen de envío internacional

# Términos de bazar y cocina a vigilar (se les aplica el filtro internacional).
QUERY_TERMS = [
    "utensilios cocina",
    "bazar cocina",
    "pelador verduras",
    "colador cocina",
    "molde reposteria",
    "rallador cocina",
    "set cuchillos cocina",
    "organizador cocina",
]
LIMIT_PER_TERM = 50
REQUEST_PAUSE = 0.6
OUTPUT = os.environ.get("RADAR_OUTPUT", "data.json")

CLIENT_ID = os.environ.get("ML_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "").strip()
REFRESH_TOKEN = os.environ.get("ML_REFRESH_TOKEN", "").strip()
GH_PAT = os.environ.get("GH_PAT", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "").strip()


def write_output(items, mode, note=""):
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    items.sort(key=lambda x: (x.get("price") or 1e12))
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "site": SITE,
        "mode": mode,
        "filter": f"SHIPPING_ORIGIN={INTL_ORIGIN_ID} (internacional)",
        "query_terms": QUERY_TERMS,
        "count": len(items),
        "items": items,
    }
    if note:
        out["note"] = note
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"OK · {len(items)} artículos -> {OUTPUT} (modo {mode})")


def get_access_token():
    """Renueva el token y persiste el nuevo refresh token."""
    tok = mlauth.refresh(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
    access = tok.get("access_token")
    new_refresh = tok.get("refresh_token")
    if not access:
        raise RuntimeError(f"refresh sin access_token: {tok}")
    if new_refresh and new_refresh != REFRESH_TOKEN and GH_PAT and REPO:
        try:
            mlauth.update_repo_secret(REPO, GH_PAT, "ML_REFRESH_TOKEN", new_refresh)
            print("  · refresh token rotado y guardado en el secreto del repo")
        except Exception as e:
            print(f"  ! No pude guardar el nuevo refresh token: {e}", file=sys.stderr)
    return access


def search(term, access):
    q = urllib.parse.quote(term)
    url = (f"https://api.mercadolibre.com/sites/{SITE}/search"
           f"?q={q}&limit={LIMIT_PER_TERM}&shipping_origin={INTL_ORIGIN_ID}")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {access}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("results", [])


def item_signals(it):
    labels = ["Envío internacional (filtro de ML)"]
    addr = it.get("seller_address") or {}
    country = (addr.get("country") or {}).get("name") or (addr.get("country") or {}).get("id")
    if country and str(country).upper() not in ("AR", "ARGENTINA"):
        labels.append(f"Vendedor: {country}")
    if str(it.get("currency_id", "")).upper() == "USD":
        labels.append("Precio en USD")
    return list(dict.fromkeys(labels))


def probe_endpoints(access):
    """Diagnóstico: prueba varios endpoints con el MISMO access token."""
    import urllib.error
    tests = [
        ("users/me", "https://api.mercadolibre.com/users/me"),
        ("search plano", "https://api.mercadolibre.com/sites/MLA/search?q=pelador&limit=1"),
        ("search intl", "https://api.mercadolibre.com/sites/MLA/search?q=pelador&limit=1&shipping_origin=10215069"),
        ("products/search", "https://api.mercadolibre.com/products/search?site_id=MLA&q=pelador&status=active"),
        ("highlights", "https://api.mercadolibre.com/highlights/MLA/category/MLA1574"),
    ]
    for name, url in tests:
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}"})
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read(220).decode("utf-8", "replace").replace("\n", " ")
                print(f"  [probe] {name}: HTTP {r.status} · {body[:180]}")
        except urllib.error.HTTPError as e:
            body = e.read(220).decode("utf-8", "replace").replace("\n", " ") if e.fp else ""
            print(f"  [probe] {name}: HTTP {e.code} · {body[:180]}")
        except Exception as e:
            print(f"  [probe] {name}: {type(e).__name__}: {e}")


def main():
    if not (CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN):
        print("Faltan credenciales de la API de ML. Escribo estado de espera.")
        write_output([], "esperando_config",
                     "Configurá los secretos ML_CLIENT_ID, ML_CLIENT_SECRET y "
                     "ML_REFRESH_TOKEN para activar el radar.")
        return

    print(f"Radar Importados · sitio={SITE} · modo=API")
    access = get_access_token()

    if os.environ.get("RADAR_DEBUG"):
        probe_endpoints(access)

    found = {}
    for term in QUERY_TERMS:
        try:
            results = search(term, access)
        except Exception as e:
            print(f"  ! Búsqueda falló en '{term}': {e}", file=sys.stderr)
            continue
        print(f"  · '{term}': {len(results)} resultados")
        for it in results:
            found[it.get("id")] = {
                "title": (it.get("title") or "").strip(),
                "price": it.get("price"),
                "currency": it.get("currency_id", "ARS"),
                "permalink": it.get("permalink", ""),
                "thumbnail": (it.get("thumbnail") or "").replace("http://", "https://"),
                "seller": ((it.get("seller") or {}).get("nickname")
                           or str((it.get("seller") or {}).get("id", "")) or "—"),
                "confidence": "alta",
                "signals": item_signals(it),
            }
        time.sleep(REQUEST_PAUSE)

    write_output(list(found.values()), "API")


if __name__ == "__main__":
    main()
