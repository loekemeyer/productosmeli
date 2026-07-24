#!/usr/bin/env python3
"""
Radar Importados — agente diario para Mercado Libre Argentina (MLA).

Busca términos de bazar/cocina y conserva SOLO los artículos que se consiguen
mediante envío internacional (productos importados / Cross-Border Trade, "CBT").

Genera `data.json`, que el panel `index.html` muestra.

Dos modos de acceso a datos:
  1) API oficial  -> si existe la variable de entorno ML_ACCESS_TOKEN.
                     Más estable y respeta los Términos de ML.
  2) Scraping HTML -> respaldo si no hay token. Más frágil.

Uso:
    python agent.py                 # usa config por defecto (abajo)
    ML_ACCESS_TOKEN=xxx python agent.py

Notas de honestidad:
  - Las heurísticas de "envío internacional" son best-effort. Conviene validarlas
    contra resultados reales y ajustar los umbrales. Marcamos cada ítem con un
    nivel de confianza (alta/media/baja) para que ninguna señal débil pase como
    certeza.
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
# Términos de bazar y cocina a vigilar. Editá/ampliá esta lista libremente.
QUERY_TERMS = [
    "pelador mango madera",
    "colador chino cocina",
    "molde silicona reposteria",
    "rallador tambor",
    "mortero granito cocina",
    "exprimidor citricos manual",
    "tabla de bambu cocina",
    "set cuchillos damasco",
    "prensa ajo acero",
    "espatula silicona reposteria",
    "batidor globo acero",
    "utensilios cocina importados",
]
LIMIT_PER_TERM = 50          # máx. resultados por término (API pagina de a 50)
MIN_CONFIDENCE = "baja"      # nivel mínimo a incluir: alta | media | baja
REQUEST_PAUSE = 1.2          # segundos entre requests (buena vecindad)
OUTPUT = os.environ.get("RADAR_OUTPUT", "data.json")
UA = "RadarImportados/1.0 (+github-actions; kitchen-bazaar-monitor)"

TOKEN = os.environ.get("ML_ACCESS_TOKEN", "").strip()

# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _get(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.status


# --------------------------------------------------------------------------- #
# Detección de "solo envío internacional"
# --------------------------------------------------------------------------- #
# Palabras que suelen indicar importación / envío desde el exterior.
INTL_HINTS = [
    "envío internacional", "envio internacional", "international",
    "producto importado", "importado", "cross border", "cbt",
    "desde el exterior", "demora", "aduana", "correo internacional",
]


def _confidence(signals):
    """Deriva un nivel de confianza a partir de la cantidad/calidad de señales."""
    strong = {"tag:cbt", "tag:international", "intl_delivery_mode", "seller_foreign"}
    strong_hits = sum(1 for s in signals if s in strong)
    if strong_hits >= 2:
        return "alta"
    if strong_hits == 1 or len(signals) >= 2:
        return "media"
    return "baja"


def classify_api_item(item):
    """
    Recibe un ítem del endpoint de búsqueda de la API y decide si es
    'solo envío internacional'. Devuelve (es_internacional, signals[], labels[]).

    Señales usadas (según disponibilidad en la respuesta de ML):
      - item['tags'] contiene 'cbt' / 'catalog_boost' / 'international'...
      - item['international_delivery_mode'] != 'none'
      - item['shipping']['tags'] con marcas internacionales
      - moneda USD
      - vendedor / dirección fuera de Argentina
    """
    signals, labels = [], []
    tags = [str(t).lower() for t in (item.get("tags") or [])]

    if any("cbt" in t for t in tags):
        signals.append("tag:cbt"); labels.append("Producto importado (CBT)")
    if any("international" in t for t in tags):
        signals.append("tag:international"); labels.append("Envío internacional")

    idm = str(item.get("international_delivery_mode", "none")).lower()
    if idm and idm != "none":
        signals.append("intl_delivery_mode"); labels.append("Envío internacional")

    shipping = item.get("shipping") or {}
    ship_tags = [str(t).lower() for t in (shipping.get("tags") or [])]
    if any("international" in t or "cbt" in t for t in ship_tags):
        signals.append("tag:international"); labels.append("Envío internacional")

    if str(item.get("currency_id", "")).upper() == "USD":
        signals.append("currency_usd"); labels.append("Precio en USD")

    addr = item.get("seller_address") or {}
    country = (addr.get("country") or {}).get("id") or (addr.get("country") or {}).get("name")
    if country and str(country).upper() not in ("AR", "ARGENTINA"):
        signals.append("seller_foreign"); labels.append("Vendedor del exterior")

    # dedup preservando orden
    labels = list(dict.fromkeys(labels))
    is_intl = len(signals) > 0
    return is_intl, signals, labels


# --------------------------------------------------------------------------- #
# Modo API oficial
# --------------------------------------------------------------------------- #
def search_api(term):
    q = urllib.parse.quote(term)
    url = f"https://api.mercadolibre.com/sites/{SITE}/search?q={q}&limit={LIMIT_PER_TERM}"
    body, status = _get(url, headers={"User-Agent": UA, "Authorization": f"Bearer {TOKEN}"})
    if status != 200:
        raise RuntimeError(f"API status {status} para '{term}'")
    return json.loads(body).get("results", [])


def run_api():
    found = {}
    for term in QUERY_TERMS:
        try:
            results = search_api(term)
        except Exception as e:
            print(f"  ! API falló en '{term}': {e}", file=sys.stderr)
            continue
        for it in results:
            is_intl, signals, labels = classify_api_item(it)
            if not is_intl:
                continue
            conf = _confidence(signals)
            if _rank(conf) > _rank(MIN_CONFIDENCE):
                continue
            found[it.get("id")] = {
                "title": it.get("title", "").strip(),
                "price": it.get("price"),
                "currency": it.get("currency_id", "ARS"),
                "permalink": it.get("permalink", ""),
                "thumbnail": (it.get("thumbnail") or "").replace("http://", "https://"),
                "seller": ((it.get("seller") or {}).get("nickname")
                           or str((it.get("seller") or {}).get("id", "")) or "—"),
                "confidence": conf,
                "signals": labels or ["Señal de importación"],
            }
        time.sleep(REQUEST_PAUSE)
    return list(found.values())


# --------------------------------------------------------------------------- #
# Modo respaldo: scraping del listado público
# --------------------------------------------------------------------------- #
def run_scrape():
    found = {}
    for term in QUERY_TERMS:
        slug = urllib.parse.quote(term.replace(" ", "-"))
        url = f"https://listado.mercadolibre.com.ar/{slug}"
        try:
            body, status = _get(url, headers={"User-Agent": UA})
        except Exception as e:
            print(f"  ! Scrape falló en '{term}': {e}", file=sys.stderr)
            time.sleep(REQUEST_PAUSE)
            continue

        # Cada tarjeta suele venir en un bloque <li class="ui-search-layout__item">.
        for block in re.split(r'ui-search-layout__item', body)[1:]:
            low = block.lower()
            if not any(h in low for h in INTL_HINTS):
                continue  # sin señal internacional -> descartar
            link = _first(r'href="(https://[^"]*mercadolibre[^"]*?)"', block)
            title = _clean(_first(r'ui-search-item__title[^>]*>([^<]+)<', block)
                           or _first(r'class="poly-component__title[^>]*>([^<]+)<', block))
            price = _first(r'andes-money-amount__fraction[^>]*>([\d\.]+)<', block)
            if not link or not title:
                continue
            labels = []
            if "internacional" in low:
                labels.append("Envío internacional")
            if "importado" in low:
                labels.append("Producto importado")
            if "demora" in low or "aduana" in low:
                labels.append("Demora de importación")
            conf = "media" if len(labels) >= 2 else "baja"
            key = link.split("#")[0]
            found[key] = {
                "title": title,
                "price": int(price.replace(".", "")) if price else None,
                "currency": "ARS",
                "permalink": key,
                "thumbnail": "",
                "seller": "—",
                "confidence": conf,
                "signals": labels or ["Señal de importación (scraping)"],
            }
        time.sleep(REQUEST_PAUSE)
    return list(found.values())


def _first(pattern, text):
    m = re.search(pattern, text)
    return m.group(1) if m else ""


def _clean(s):
    return html.unescape(s).strip() if s else s


_RANKS = {"alta": 0, "media": 1, "baja": 2}
def _rank(c):  # noqa: E704
    return _RANKS.get(c, 9)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    mode = "API" if TOKEN else "SCRAPE"
    print(f"Radar Importados · sitio={SITE} · modo={mode} · términos={len(QUERY_TERMS)}")
    items = run_api() if TOKEN else run_scrape()

    # Orden: confianza y luego precio.
    items.sort(key=lambda x: (_rank(x["confidence"]), x.get("price") or 1e12))

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "site": SITE,
        "mode": mode,
        "query_terms": QUERY_TERMS,
        "count": len(items),
        "items": items,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"OK · {len(items)} artículos importados -> {OUTPUT}")


if __name__ == "__main__":
    main()
