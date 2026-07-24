#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar Importados — navegador real (Playwright) + comparación local + historial.

- Lee ML AR filtrado por ENVÍO INTERNACIONAL (bazar/cocina) con un Chrome real.
- Para cada producto NUEVO, busca su equivalente en la oferta local y compara.
- ACUMULA día a día (recuerda lo de antes; marca lo nuevo con su fecha).
- Excluye palabras que no te interesan (archivo no-me-interesa.txt, opcional).
- Sube data.json al repo para que el panel web se actualice.

Config (variables de entorno, del .bat o la consola):
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
MAX_PAGES = 6
SIM_THRESHOLD = 0.45
KEEP_DAYS = 60           # cuánto tiempo conservar un artículo sin volver a verlo
MAX_STORE = 1200         # tope de artículos acumulados
BLOCKLIST_FILE = "no-me-interesa.txt"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pw-profile")

GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
GH_REPO = os.environ.get("GH_REPO", "loekemeyer/productosmeli").strip()

RESULTS_SEL = "li.ui-search-layout__item, div.poly-card, div.ui-search-result__wrapper"
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
    const soldM = (el.textContent || "").match(/([\d.]+)\s*vendidos?/i);
    out.push({ title, link,
      price: p ? p.textContent.replace(/[.\s]/g, "") : "",
      thumb: img ? (img.getAttribute("src") || img.getAttribute("data-src") || "") : "",
      sold: soldM ? soldM[1].replace(/\./g, "") : "",
      intl: (el.textContent || "").toLowerCase().includes("internacional") });
  });
  return out;
}
"""

STOP = set((
    "de del la el los las un una unos unas y o u con sin para por en a al su sus "
    "x cm mm mts mt lt ml gr kg unidad unidades pack set kit combo nuevo nueva "
    "importado importada importados importadas internacional import the of and").split())


def _txt(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _words(s):
    return [w for w in re.sub(r"[^a-z0-9 ]", " ", _txt(s)).split() if w not in STOP and len(w) > 1]


def keywords(title, n=6):
    return [w for w in _words(title) if not w.isdigit()][:n]


def similarity(a, b):
    A, B = set(_words(a)), set(_words(b))
    if not A or not B:
        return 0.0
    inter = len(A & B)
    return round(max(inter / len(A | B), 0.5 * inter / len(A | B) + 0.5 * inter / len(A)), 3)


# --------------------------------------------------------------------------- #
def today_str():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).date().isoformat()


def load_blocklist():
    words = []
    if os.path.exists(BLOCKLIST_FILE):
        for line in open(BLOCKLIST_FILE, encoding="utf-8", errors="replace"):
            w = line.strip()
            if w and not w.startswith("#"):
                words.append(_txt(w))
    return words


def is_blocked(title, words):
    t = _txt(title)
    return any(w in t for w in words)


def load_existing():
    url = f"https://raw.githubusercontent.com/{GH_REPO}/main/data.json"
    for src in (url, "data.json"):
        try:
            if src.startswith("http"):
                with urllib.request.urlopen(src, timeout=20) as r:
                    return json.loads(r.read().decode("utf-8", "replace"))
            return json.load(open(src, encoding="utf-8"))
        except Exception:
            continue
    return {}


def gh_put_file(path, content_bytes, message):
    if not GH_TOKEN:
        print("  ! Sin GH_TOKEN: no subo a GitHub.")
        return
    api = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
    headers = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
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
def wait_results(page, allow_challenge=True):
    try:
        page.wait_for_selector(RESULTS_SEL, timeout=12000)
        return True
    except PWTimeout:
        pass
    if not allow_challenge:
        return False
    print("\n  ⚠️  Mercado Libre pidió una verificación. Resolvéla en la ventana y esperá…\n")
    try:
        page.wait_for_selector(RESULTS_SEL, timeout=180000)
        return True
    except PWTimeout:
        return False


def extract(page):
    page.wait_for_timeout(1100)
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
            page.wait_for_timeout(900)
    return list(items.values())


def search_local(page, query):
    url = "https://listado.mercadolibre.com.ar/" + urllib.parse.quote("-".join(query))
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        return []
    if not wait_results(page):
        return []
    return extract(page)


def to_item(c):
    return {"title": c["title"],
            "price": int(c["price"]) if str(c.get("price", "")).isdigit() else None,
            "currency": "ARS", "permalink": c["link"], "thumbnail": c.get("thumb", "") or "",
            "sold": int(c["sold"]) if str(c.get("sold", "")).isdigit() else None}


def classify(page, c):
    """Devuelve ('only', None, 0) o ('local', item_local, score)."""
    kw = keywords(c["title"])
    best, best_score = None, 0.0
    if kw:
        for r in search_local(page, kw):
            if r["link"] == c["link"] or r.get("intl"):
                continue
            s = similarity(c["title"], r["title"])
            if s > best_score:
                best, best_score = r, s
        page.wait_for_timeout(800)
    if best and best_score >= SIM_THRESHOLD:
        return "local", to_item(best), best_score
    return "only", None, 0.0


# --------------------------------------------------------------------------- #
def main():
    day = today_str()
    block = load_blocklist()
    if block:
        print(f"  · palabras a excluir: {', '.join(block)}")

    # 1) Reconstruir el historial acumulado
    prev = load_existing()
    store = {}   # key(permalink) -> registro
    for it in prev.get("only_import", []):
        store[it["permalink"]] = {"kind": "only", "import": it, "local": None, "score": 0.0,
                                  "first_seen": it.get("first_seen", day), "last_seen": it.get("last_seen", day)}
    for pr in prev.get("also_local", []):
        imp = pr["import"]
        store[imp["permalink"]] = {"kind": "local", "import": imp, "local": pr.get("local"),
                                   "score": pr.get("score", 0.0),
                                   "first_seen": imp.get("first_seen", day), "last_seen": imp.get("last_seen", day)}
    print(f"  · historial previo: {len(store)} artículos")

    # 2) Escanear importados de hoy
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE_DIR, headless=False, locale="es-AR",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        intl = scrape_international(page)
        intl = [c for c in intl if not is_blocked(c["title"], block)]
        print(f"\n  {len(intl)} importados hoy. Verificando los nuevos…\n")

        nuevos = 0
        for i, c in enumerate(intl, 1):
            key = c["link"]
            if key in store:
                store[key]["import"].update(to_item(c))      # refresca precio/imagen
                store[key]["last_seen"] = day
                continue
            nuevos += 1
            print(f"  · nuevo [{i}/{len(intl)}] {' '.join(keywords(c['title']))[:48]}…")
            kind, local, score = classify(page, c)
            store[key] = {"kind": kind, "import": to_item(c), "local": local, "score": score,
                          "first_seen": day, "last_seen": day}
        ctx.close()
    print(f"\n  {nuevos} nuevos agregados.")

    # 3) Podar viejos, aplicar bloqueo, limitar tamaño
    def age_days(rec):
        try:
            d = datetime.date.fromisoformat(rec["last_seen"])
            return (datetime.date.fromisoformat(day) - d).days
        except Exception:
            return 0
    recs = [r for r in store.values()
            if age_days(r) <= KEEP_DAYS and not is_blocked(r["import"]["title"], block)]
    recs.sort(key=lambda r: (r["first_seen"], r["import"].get("price") or 0), reverse=True)
    recs = recs[:MAX_STORE]

    # 4) Armar la salida con fechas y marca "nuevo"
    only_import, also_local = [], []
    for r in recs:
        imp = dict(r["import"])
        imp["first_seen"] = r["first_seen"]
        imp["last_seen"] = r["last_seen"]
        imp["nuevo"] = (r["first_seen"] == day)
        if r["kind"] == "local" and r.get("local"):
            also_local.append({"score": r["score"], "import": imp, "local": r["local"]})
        else:
            only_import.append(imp)

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).isoformat(timespec="seconds"),
        "site": "MLA", "mode": "navegador",
        "filter": f"SHIPPING_ORIGIN={INTL_ORIGIN_ID} (internacional)",
        "count_only": len(only_import), "count_local": len(also_local),
        "only_import": only_import, "also_local": also_local,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nOK · {len(only_import)} solo importados · {len(also_local)} también local "
          f"({nuevos} nuevos hoy) -> data.json")
    try:
        gh_put_file("data.json", json.dumps(out, ensure_ascii=False, indent=2).encode(),
                    f"Actualizar resultados {day}")
    except Exception as e:
        print(f"  ! No pude subir a GitHub: {e}")


if __name__ == "__main__":
    main()
    if os.name == "nt":
        input("\nListo. Apretá Enter para cerrar…")
