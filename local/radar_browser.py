#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar Importados — versión con NAVEGADOR REAL (Playwright) + comparación local.

1) Lee la búsqueda de Mercado Libre AR filtrada por ENVÍO INTERNACIONAL
   (bazar/cocina) usando un Chrome real (así ML no lo bloquea).
2) Para CADA producto importado, busca el mismo producto en la oferta normal
   de ML y, comparando títulos (similitud) + precio, decide si TAMBIÉN se
   consigue en el país.
3) Separa en dos grupos: "solo importado" y "también local" (con la publicación
   local emparejada, para comparar).
4) Sube data.json al repo para que el panel web se actualice.

Config (variables de entorno, del .bat o de la consola):
  GH_TOKEN  -> token de GitHub (Contents: Read and write)
  GH_REPO   -> "loekemeyer/productosmeli"
"""

import os
import re
import json
import base64
import unicodedata
import datetime
import urllib.request
import urllib.parse

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

INTL_ORIGIN_ID = "10215069"
LISTING_URLS = [
    "https://listado.mercadolibre.com.ar/hogar-muebles-jardin/bazar-cocina/nuevo/"
    "utensilios_NoIndex_True_SHIPPING*ORIGIN_" + INTL_ORIGIN_ID,
]
MAX_PAGES = 6            # páginas de la lista de importados
SIM_THRESHOLD = 0.45     # qué tan parecido debe ser el título local para contar
MAX_VERIFY = 200         # tope de productos a verificar por corrida
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pw-profile")

GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
GH_REPO = os.environ.get("GH_REPO", "loekemeyer/productosmeli").strip()

RESULTS_SEL = "li.ui-search-layout__item, div.poly-card, div.ui-search-result__wrapper"

# JS que extrae las tarjetas visibles (título, link, precio, miniatura, si es internacional)
EXTRACT_JS = r"""
() => {
  const cards = document.querySelectorAll(
    "li.ui-search-layout__item, div.poly-card, div.ui-search-result__wrapper");
  const out = [];
  cards.forEach(el => {
    const a = el.querySelector("a.poly-component__title, a.ui-search-link, a[href*='mercadolibre.com.ar']");
    const t = el.querySelector(".poly-component__title, .ui-search-item__title");
    const p = el.querySelector(".andes-money-amount__fraction");
    const img = el.querySelector("img");
    const title = ((t && t.textContent) || (a && a.textContent) || "").trim();
    const link = (a && a.href) ? a.href.split("#")[0].split("?")[0] : "";
    if (!title || !link) return;
    const txt = (el.textContent || "").toLowerCase();
    out.push({
      title, link,
      price: p ? p.textContent.replace(/[.\s]/g, "") : "",
      thumb: img ? (img.getAttribute("src") || img.getAttribute("data-src") || "") : "",
      intl: txt.includes("internacional")
    });
  });
  return out;
}
"""

# --------------------------------------------------------------------------- #
# Similitud de títulos
# --------------------------------------------------------------------------- #
STOP = set((
    "de del la el los las un una unos unas y o u con sin para por en a al su sus "
    "x cm mm mts mt lt ml gr kg unidad unidades pack set kit combo nuevo nueva "
    "importado importada importados importadas internacional import the of and").split())


def _norm_words(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return [w for w in s.split() if w not in STOP and len(w) > 1]


def keywords(title, n=6):
    kw = [w for w in _norm_words(title) if not w.isdigit()]
    return kw[:n]


def similarity(a_title, b_title):
    A, B = set(_norm_words(a_title)), set(_norm_words(b_title))
    if not A or not B:
        return 0.0
    inter = len(A & B)
    jacc = inter / len(A | B)
    cov = inter / len(A)          # proporción de palabras del importado presentes
    return round(max(jacc, 0.5 * jacc + 0.5 * cov), 3)


# --------------------------------------------------------------------------- #
# GitHub
# --------------------------------------------------------------------------- #
def gh_put_file(path, content_bytes, message):
    if not GH_TOKEN:
        print("  ! Sin GH_TOKEN: no subo a GitHub.")
        return
    api = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
    headers = {"Authorization": f"Bearer {GH_TOKEN}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "radar-local"}
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=30) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass
    payload = {"message": message, "content": base64.b64encode(content_bytes).decode()}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(api, data=json.dumps(payload).encode(), method="PUT", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    print(f"  · subido a GitHub: {path}")


# --------------------------------------------------------------------------- #
# Navegador
# --------------------------------------------------------------------------- #
def wait_results(page, allow_challenge=True):
    try:
        page.wait_for_selector(RESULTS_SEL, timeout=12000)
        return True
    except PWTimeout:
        pass
    if not allow_challenge:
        return False
    print("\n  ⚠️  Mercado Libre pidió una verificación en la ventana.")
    print("     Resolvéla ahí y esperá; cuando cargue la lista, sigue solo.\n")
    try:
        page.wait_for_selector(RESULTS_SEL, timeout=180000)
        return True
    except PWTimeout:
        return False


def extract(page):
    page.wait_for_timeout(1200)
    try:
        return page.evaluate(EXTRACT_JS)
    except Exception:
        return []


def scrape_international(page):
    items = {}
    for base in LISTING_URLS:
        url, pages = base, 0
        while url and pages < MAX_PAGES:
            print(f"  · importados, página {pages + 1}…")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"  ! error al abrir: {e}")
                break
            if not wait_results(page):
                break
            cards = extract(page)
            print(f"    encontrados: {len(cards)}")
            for c in cards:
                items[c["link"]] = c
            if not cards:
                break
            try:
                url = page.evaluate(
                    "() => { const a = document.querySelector("
                    "\"a[title='Siguiente'], .andes-pagination__button--next a\");"
                    " return a ? a.href : ''; }")
            except Exception:
                url = ""
            pages += 1
            page.wait_for_timeout(1000)
    return list(items.values())


def search_local(page, query):
    """Busca `query` en la oferta normal de ML y devuelve las tarjetas."""
    slug = "-".join(query)
    url = "https://listado.mercadolibre.com.ar/" + urllib.parse.quote(slug)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        return []
    if not wait_results(page, allow_challenge=True):
        return []
    return extract(page)


def to_item(c, extra=None):
    it = {
        "title": c["title"],
        "price": int(c["price"]) if str(c.get("price", "")).isdigit() else None,
        "currency": "ARS",
        "permalink": c["link"],
        "thumbnail": c.get("thumb", "") or "",
    }
    if extra:
        it.update(extra)
    return it


def main():
    only_import, also_local = [], []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=False, locale="es-AR",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        intl = scrape_international(page)
        print(f"\n  {len(intl)} importados encontrados. Verificando cuáles hay también local…\n")

        for i, c in enumerate(intl[:MAX_VERIFY], 1):
            kw = keywords(c["title"])
            print(f"  · [{i}/{min(len(intl), MAX_VERIFY)}] {' '.join(kw)[:50]}…")
            best, best_score = None, 0.0
            if kw:
                for r in search_local(page, kw):
                    if r["link"] == c["link"] or r.get("intl"):
                        continue  # descarto la misma publi y las internacionales
                    s = similarity(c["title"], r["title"])
                    if s > best_score:
                        best, best_score = r, s
                page.wait_for_timeout(900)

            imp = to_item(c, {"seller": "—", "confidence": "alta",
                              "signals": ["Envío internacional (filtro de ML)"]})
            if best and best_score >= SIM_THRESHOLD:
                also_local.append({
                    "score": best_score,
                    "import": imp,
                    "local": to_item(best),
                })
                print(f"      ↳ también local (parecido {best_score})")
            else:
                only_import.append(imp)

        ctx.close()

    only_import.sort(key=lambda x: (x.get("price") or 1e12))
    also_local.sort(key=lambda x: -x["score"])
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "site": "MLA", "mode": "navegador",
        "filter": f"SHIPPING_ORIGIN={INTL_ORIGIN_ID} (internacional)",
        "query_terms": ["bazar-cocina/utensilios"],
        "count_only": len(only_import),
        "count_local": len(also_local),
        "only_import": only_import,
        "also_local": also_local,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nOK · {len(only_import)} solo importados · {len(also_local)} también local -> data.json")
    try:
        gh_put_file("data.json", json.dumps(out, ensure_ascii=False, indent=2).encode(),
                    f"Actualizar resultados {now.date()} (navegador)")
    except Exception as e:
        print(f"  ! No pude subir a GitHub: {e}")


if __name__ == "__main__":
    main()
    if os.name == "nt":
        input("\nListo. Apretá Enter para cerrar…")
