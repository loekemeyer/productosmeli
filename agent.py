#!/usr/bin/env python3
"""
Radar Importados — agente diario para Mercado Libre Argentina (MLA).

Reúne artículos de bazar y cocina que SOLO se consiguen con envío internacional
(productos importados / Cross-Border Trade), usando el propio filtro de origen
de envío internacional de Mercado Libre. Genera `data.json`, que el panel
`index.html` muestra.

Clave: en Mercado Libre AR, el filtro de la URL
    ..._SHIPPING*ORIGIN_10215069
lista únicamente publicaciones cuyo origen de envío es INTERNACIONAL. Por eso
todo lo que aparece en esas páginas es, por construcción, envío internacional
—no hace falta adivinar con heurísticas—. Igual conservamos señales extra
(origen, moneda) para dar detalle.

Dos modos:
  1) SCRAPE (por defecto) -> recorre las URLs de listado ya filtradas.
  2) API (si hay ML_ACCESS_TOKEN) -> usa el endpoint oficial con el mismo
     filtro de origen internacional. Más estable y respeta los Términos de ML.

Uso:
    python agent.py
    ML_ACCESS_TOKEN=xxx python agent.py
"""

import json
import os
import re
import sys
import time
import html
import datetime
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
SITE = "MLA"  # Argentina

# ID del filtro "origen de envío = internacional" en Mercado Libre AR.
INTL_ORIGIN_ID = "10215069"

# URLs de listado YA FILTRADAS por envío internacional. Cada una corresponde a
# una categoría/búsqueda. Agregá o cambiá las que quieras: entrá a Mercado Libre,
# filtrá por "Envío internacional" y pegá acá la URL resultante.
LISTING_URLS = [
    # Bazar y cocina -> Utensilios, nuevos, solo envío internacional.
    "https://listado.mercadolibre.com.ar/hogar-muebles-jardin/bazar-cocina/nuevo/"
    "utensilios_NoIndex_True_SHIPPING*ORIGIN_" + INTL_ORIGIN_ID,
]

# Para el modo API: términos a buscar (se les aplica el filtro internacional).
QUERY_TERMS = [
    "utensilios cocina",
    "bazar cocina",
    "pelador verduras",
    "colador cocina",
    "molde reposteria",
    "rallador cocina",
]

MAX_PAGES = 6                # máx. páginas por URL de listado (scrape)
LIMIT_PER_TERM = 50          # resultados por término (API pagina de a 50)
REQUEST_PAUSE = 1.4          # segundos entre requests (buena vecindad)
OUTPUT = os.environ.get("RADAR_OUTPUT", "data.json")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 RadarImportados/1.1")

TOKEN = os.environ.get("ML_ACCESS_TOKEN", "").strip()

_RANKS = {"alta": 0, "media": 1, "baja": 2}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _get(url, headers=None, timeout=30):
    hdrs = {"User-Agent": UA, "Accept-Language": "es-AR,es;q=0.9"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.status


def _first(pattern, text, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1) if m else ""


def _clean(s):
    return html.unescape(s).strip() if s else s


# --------------------------------------------------------------------------- #
# Modo SCRAPE — recorre listados ya filtrados por envío internacional
# --------------------------------------------------------------------------- #
_PROD_LINK = re.compile(
    r'href="(https://(?:articulo\.)?(?:www\.)?mercadolibre\.com\.ar/'
    r'(?:MLA-?\d|p/MLA)[^"#?]*)"'
)


def _split_blocks(body):
    """Divide el HTML en bloques-tarjeta probando varios envoltorios de ML."""
    for marker in ("ui-search-layout__item", "poly-card__content",
                   "poly-card", "ui-search-result__wrapper"):
        parts = re.split(marker, body)
        if len(parts) > 1:
            return parts[1:]
    return []


def _parse_cards(body):
    """Extrae (title, link, price, thumbnail) de cada tarjeta del listado."""
    out = []
    for block in _split_blocks(body):
        m = _PROD_LINK.search(block)
        link = m.group(1) if m else ""
        title = _clean(
            _first(r'poly-component__title"[^>]*>([^<]+)<', block)
            or _first(r'ui-search-item__title[^>]*>([^<]+)<', block)
            or _first(r'class="poly-component__title[^"]*"[^>]*>\s*<[^>]*>([^<]+)<', block)
            or _first(r'<h[23][^>]*>([^<]{5,})<', block)
        )
        # El título a veces viene como texto del propio <a> del link.
        if not title and m:
            title = _clean(_first(re.escape(m.group(0)) + r'[^>]*>([^<]+)<', block))
        price = _first(r'andes-money-amount__fraction[^>]*>([\d\.]+)<', block)
        thumb = _first(r'(?:data-src|src)="(https://http2\.mlstatic\.com/[^"]+)"', block)
        if not link or not title:
            continue
        out.append({
            "title": title,
            "link": link.split("#")[0].split("?")[0],
            "price": int(price.replace(".", "")) if price else None,
            "thumbnail": thumb,
        })
    return out


def _diagnose(body, status):
    """Imprime pistas del HTML recibido para depurar sin acceso local a ML."""
    low = body.lower()
    title = _clean(_first(r'<title[^>]*>([^<]+)<', body)) or "(sin title)"
    print("  [diag] HTTP", status, "· bytes", len(body), "· <title>:", title[:90])
    markers = ["ui-search-layout__item", "poly-card", "poly-component__title",
               "andes-money-amount__fraction", "ui-search-result", "ui-search-results"]
    print("  [diag] marcadores:",
          {k: low.count(k.lower()) for k in markers})
    prod_links = len(_PROD_LINK.findall(body))
    print("  [diag] links de producto detectados:", prod_links)
    for flag in ("captcha", "robot", "unusual traffic", "access denied",
                 "nada por acá", "no encontramos", "sin resultados"):
        if flag in low:
            print("  [diag] ⚠ posible bloqueo/vacío:", flag)
    # Muestra el HTML alrededor del primer link de producto (para ver la tarjeta).
    m = _PROD_LINK.search(body)
    if m:
        i = max(0, m.start() - 700)
        print("  [diag] --- excerpt tarjeta ---")
        print(body[i:m.start() + 700])
        print("  [diag] --- fin excerpt ---")
    else:
        print("  [diag] --- primeros 1200 chars ---")
        print(body[:1200])


def _next_url(body):
    """Encuentra la URL de la página siguiente del listado, si existe."""
    nxt = _first(r'<link rel="next" href="([^"]+)"', body)
    if nxt:
        return html.unescape(nxt)
    # Botón "Siguiente" de la paginación de Andes.
    m = re.search(r'andes-pagination__button--next[^>]*>.*?href="([^"]+)"', body, re.S)
    if m:
        return html.unescape(m.group(1))
    m = re.search(r'href="([^"]+)"[^>]*title="Siguiente"', body)
    return html.unescape(m.group(1)) if m else ""


def run_scrape():
    found = {}
    for base in LISTING_URLS:
        url, pages = base, 0
        while url and pages < MAX_PAGES:
            try:
                body, status = _get(url)
            except Exception as e:
                print(f"  ! Scrape falló ({url[:70]}...): {e}", file=sys.stderr)
                break
            cards = _parse_cards(body)
            print(f"  · página {pages + 1}: {len(cards)} artículos")
            if pages == 0 and (not cards or os.environ.get("RADAR_DEBUG")):
                _diagnose(body, status)
            for c in cards:
                # Todo lo de estas páginas ya está filtrado a envío internacional.
                found[c["link"]] = {
                    "title": c["title"],
                    "price": c["price"],
                    "currency": "ARS",
                    "permalink": c["link"],
                    "thumbnail": c["thumbnail"] or "",
                    "seller": "—",
                    "confidence": "alta",
                    "signals": ["Envío internacional (filtro de ML)"],
                }
            if not cards:
                break
            url = _next_url(body)
            pages += 1
            time.sleep(REQUEST_PAUSE)
    return list(found.values())


# --------------------------------------------------------------------------- #
# Modo API — endpoint oficial con el mismo filtro de origen internacional
# --------------------------------------------------------------------------- #
def _api_signals(item):
    labels = ["Envío internacional (filtro de ML)"]
    addr = item.get("seller_address") or {}
    country = (addr.get("country") or {}).get("name") or (addr.get("country") or {}).get("id")
    if country and str(country).upper() not in ("AR", "ARGENTINA"):
        labels.append(f"Vendedor: {country}")
    if str(item.get("currency_id", "")).upper() == "USD":
        labels.append("Precio en USD")
    return list(dict.fromkeys(labels))


def run_api():
    found = {}
    for term in QUERY_TERMS:
        q = urllib.parse.quote(term)
        url = (f"https://api.mercadolibre.com/sites/{SITE}/search"
               f"?q={q}&limit={LIMIT_PER_TERM}&shipping_origin={INTL_ORIGIN_ID}")
        try:
            body, status = _get(url, headers={"Authorization": f"Bearer {TOKEN}"})
            if status != 200:
                raise RuntimeError(f"status {status}")
            results = json.loads(body).get("results", [])
        except Exception as e:
            print(f"  ! API falló en '{term}': {e}", file=sys.stderr)
            continue
        print(f"  · '{term}': {len(results)} artículos")
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
                "signals": _api_signals(it),
            }
        time.sleep(REQUEST_PAUSE)
    return list(found.values())


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    mode = "API" if TOKEN else "SCRAPE"
    print(f"Radar Importados · sitio={SITE} · modo={mode}")
    items = run_api() if TOKEN else run_scrape()

    items.sort(key=lambda x: (_RANKS.get(x["confidence"], 9), x.get("price") or 1e12))

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "site": SITE,
        "mode": mode,
        "filter": f"SHIPPING_ORIGIN={INTL_ORIGIN_ID} (internacional)",
        "query_terms": QUERY_TERMS if TOKEN else [u.split("/nuevo/")[-1].split("_")[0]
                                                  for u in LISTING_URLS],
        "count": len(items),
        "items": items,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"OK · {len(items)} artículos importados -> {OUTPUT}")


if __name__ == "__main__":
    main()
