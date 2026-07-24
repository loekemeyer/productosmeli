#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar Importados — versión LOCAL (corre en tu PC).

Lee la búsqueda de Mercado Libre Argentina ya filtrada por ENVÍO INTERNACIONAL
(bazar y cocina) desde tu conexión de casa —donde ML no bloquea— y sube el
resultado (`data.json`) a tu repositorio, para que el panel web
https://loekemeyer.github.io/productosmeli/ se actualice solo.

No necesita cuenta de desarrollador ni token de Mercado Libre.
Solo un token de GitHub con permiso de "Contents: Read and write".

Configuración (variables de entorno, las setea radar.bat):
  GH_TOKEN  -> token de GitHub (github_pat_...)
  GH_REPO   -> "loekemeyer/productosmeli"
"""

import os
import re
import sys
import json
import time
import html
import base64
import datetime
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
INTL_ORIGIN_ID = "10215069"   # filtro ML: origen de envío internacional

# URLs de listado YA FILTRADAS por envío internacional. Podés agregar más:
# entrá a ML, filtrá por "Envío internacional" y pegá la URL acá.
LISTING_URLS = [
    "https://listado.mercadolibre.com.ar/hogar-muebles-jardin/bazar-cocina/nuevo/"
    "utensilios_NoIndex_True_SHIPPING*ORIGIN_" + INTL_ORIGIN_ID,
]
MAX_PAGES = 6
REQUEST_PAUSE = 1.5

GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
GH_REPO = os.environ.get("GH_REPO", "loekemeyer/productosmeli").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace"), r.status


def _first(pattern, text, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1) if m else ""


def _clean(s):
    return html.unescape(s).strip() if s else s


# --------------------------------------------------------------------------- #
# Parseo del listado
# --------------------------------------------------------------------------- #
_PROD_LINK = re.compile(
    r'href="(https://(?:articulo\.)?(?:www\.)?mercadolibre\.com\.ar/'
    r'(?:MLA-?\d|p/MLA)[^"#?]*)"'
)


def _split_blocks(body):
    for marker in ("ui-search-layout__item", "poly-card__content",
                   "poly-card", "ui-search-result__wrapper"):
        parts = re.split(marker, body)
        if len(parts) > 1:
            return parts[1:]
    return []


def parse_cards(body):
    out = []
    for block in _split_blocks(body):
        m = _PROD_LINK.search(block)
        link = m.group(1) if m else ""
        title = _clean(
            _first(r'poly-component__title"[^>]*>([^<]+)<', block)
            or _first(r'ui-search-item__title[^>]*>([^<]+)<', block)
            or _first(r'class="poly-component__title[^"]*"[^>]*>\s*<[^>]*>([^<]+)<', block)
        )
        if not title and m:
            title = _clean(_first(re.escape(m.group(0)) + r'[^>]*>([^<]+)<', block))
        price = _first(r'andes-money-amount__fraction[^>]*>([\d\.]+)<', block)
        thumb = _first(r'(?:data-src|src)="(https://http2\.mlstatic\.com/[^"]+)"', block)
        if not link or not title:
            continue
        out.append({
            "title": title,
            "price": int(price.replace(".", "")) if price else None,
            "permalink": link.split("#")[0].split("?")[0],
            "thumbnail": thumb or "",
        })
    return out


def next_url(body):
    nxt = _first(r'<link rel="next" href="([^"]+)"', body)
    if nxt:
        return html.unescape(nxt)
    m = re.search(r'andes-pagination__button--next[^>]*>.*?href="([^"]+)"', body, re.S)
    return html.unescape(m.group(1)) if m else ""


# --------------------------------------------------------------------------- #
# GitHub: subir un archivo (Contents API)
# --------------------------------------------------------------------------- #
def gh_put_file(path, content_bytes, message):
    if not GH_TOKEN:
        print("  ! Sin GH_TOKEN: no subo a GitHub (guardé solo local).")
        return
    api = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "radar-local",
    }
    # SHA actual (si existe) para actualizar
    sha = None
    try:
        req = urllib.request.Request(api, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
    }
    if sha:
        payload["sha"] = sha
    data = json.dumps(payload).encode()
    req = urllib.request.Request(api, data=data, method="PUT", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    print(f"  · subido a GitHub: {path}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    print("Radar Importados (local) — leyendo Mercado Libre…")
    items, captcha = {}, False
    debug_html = ""

    for base in LISTING_URLS:
        url, pages = base, 0
        while url and pages < MAX_PAGES:
            try:
                body, status = http_get(url)
            except Exception as e:
                print(f"  ! Error al leer ML: {e}")
                break
            if pages == 0 and not debug_html:
                debug_html = body
            low = body.lower()
            if "captcha" in low or "suspicious-traffic" in low or "seguridad" in _first(
                    r"<title[^>]*>([^<]+)<", body).lower():
                captcha = True
                print("  ! ML pidió verificación/captcha en esta conexión.")
                break
            cards = parse_cards(body)
            print(f"  · página {pages + 1}: {len(cards)} artículos")
            for c in cards:
                items[c["permalink"]] = {
                    "title": c["title"], "price": c["price"], "currency": "ARS",
                    "permalink": c["permalink"], "thumbnail": c["thumbnail"],
                    "seller": "—", "confidence": "alta",
                    "signals": ["Envío internacional (filtro de ML)"],
                }
            if not cards:
                break
            url = next_url(body)
            pages += 1
            time.sleep(REQUEST_PAUSE)

    result = list(items.values())
    result.sort(key=lambda x: (x.get("price") or 1e12))
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "site": "MLA", "mode": "local",
        "filter": f"SHIPPING_ORIGIN={INTL_ORIGIN_ID} (internacional)",
        "query_terms": ["bazar-cocina/utensilios"],
        "count": len(result), "items": result,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"OK · {len(result)} artículos -> data.json")

    # Subir resultados al repo (para que el panel web se actualice)
    try:
        gh_put_file("data.json", json.dumps(out, ensure_ascii=False, indent=2).encode(),
                    f"Actualizar resultados {now.date()} (local)")
    except Exception as e:
        print(f"  ! No pude subir a GitHub: {e}")

    # Si no hubo resultados, subir el HTML para diagnóstico remoto
    if (len(result) == 0 or captcha) and debug_html:
        try:
            gh_put_file("debug_page.html", debug_html.encode("utf-8"),
                        "Muestra HTML para diagnóstico")
            print("  · subí debug_page.html para revisar por qué no hubo resultados.")
        except Exception as e:
            print(f"  ! No pude subir el debug: {e}")

    if captcha:
        print("\n⚠️  ML mostró verificación incluso desde tu PC. Avisale a Claude:")
        print("    quizás haga falta la versión con navegador real.")


if __name__ == "__main__":
    main()
    if os.name == "nt":
        input("\nListo. Apretá Enter para cerrar…")
