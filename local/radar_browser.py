#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar Importados — versión con NAVEGADOR REAL (Playwright).

Abre un Chrome de verdad para leer Mercado Libre (así ML no lo bloquea como a un
programa simple), extrae los importados de bazar/cocina con envío internacional
y sube `data.json` al repo, para que el panel web se actualice.

Usa una sesión persistente (carpeta `pw-profile`): si ML muestra una
verificación, la resolvés UNA vez en la ventana y queda guardada para siempre.

Config (variables de entorno, las setea el .bat):
  GH_TOKEN  -> token de GitHub (Contents: Read and write)
  GH_REPO   -> "loekemeyer/productosmeli"
"""

import os
import json
import base64
import datetime
import urllib.request

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

INTL_ORIGIN_ID = "10215069"
LISTING_URLS = [
    "https://listado.mercadolibre.com.ar/hogar-muebles-jardin/bazar-cocina/nuevo/"
    "utensilios_NoIndex_True_SHIPPING*ORIGIN_" + INTL_ORIGIN_ID,
]
MAX_PAGES = 6
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pw-profile")

GH_TOKEN = os.environ.get("GH_TOKEN", "").strip()
GH_REPO = os.environ.get("GH_REPO", "loekemeyer/productosmeli").strip()

# JS que corre DENTRO del navegador para extraer las tarjetas de resultado.
EXTRACT_JS = r"""
() => {
  const cards = document.querySelectorAll(
    "li.ui-search-layout__item, div.poly-card, div.ui-search-result__wrapper");
  const out = [];
  cards.forEach(el => {
    const a = el.querySelector(
      "a.poly-component__title, a.ui-search-link, a[href*='mercadolibre.com.ar']");
    const t = el.querySelector(".poly-component__title, .ui-search-item__title");
    const p = el.querySelector(".andes-money-amount__fraction");
    const img = el.querySelector("img");
    const title = ((t && t.textContent) || (a && a.textContent) || "").trim();
    const link = (a && a.href) ? a.href.split("#")[0].split("?")[0] : "";
    if (!title || !link) return;
    out.push({
      title,
      link,
      price: p ? p.textContent.replace(/[.\s]/g, "") : "",
      thumb: img ? (img.getAttribute("src") || img.getAttribute("data-src") || "") : ""
    });
  });
  return out;
}
"""

RESULTS_SEL = "li.ui-search-layout__item, div.poly-card, div.ui-search-result__wrapper"


def gh_put_file(path, content_bytes, message):
    if not GH_TOKEN:
        print("  ! Sin GH_TOKEN: no subo a GitHub.")
        return
    api = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
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
    except Exception:
        pass
    payload = {"message": message, "content": base64.b64encode(content_bytes).decode()}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(api, data=json.dumps(payload).encode(), method="PUT", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    print(f"  · subido a GitHub: {path}")


def wait_for_results(page):
    """Espera los resultados. Si aparece una verificación, deja que la resuelvas."""
    try:
        page.wait_for_selector(RESULTS_SEL, timeout=15000)
        return True
    except PWTimeout:
        pass
    # Puede ser una verificación anti-bot: damos tiempo para resolverla a mano.
    print("\n  ⚠️  Mercado Libre pidió una verificación en la ventana.")
    print("     Resolvéla ahí (marcá 'no soy un robot' / lo que pida) y esperá.")
    print("     Cuando cargue la lista, sigue solo. (Hasta 3 minutos de espera)…\n")
    try:
        page.wait_for_selector(RESULTS_SEL, timeout=180000)
        return True
    except PWTimeout:
        return False


def main():
    items = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            locale="es-AR",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for base in LISTING_URLS:
            url, pages = base, 0
            while url and pages < MAX_PAGES:
                print(f"  · abriendo página {pages + 1}…")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"  ! error al abrir: {e}")
                    break

                # Aceptar banner de cookies si aparece (no es crítico).
                for txt in ("Entendido", "Aceptar cookies", "Aceptar"):
                    try:
                        page.click(f"button:has-text('{txt}')", timeout=1500)
                        break
                    except Exception:
                        pass

                if not wait_for_results(page):
                    print("  ! No cargaron resultados en esta página.")
                    break

                page.wait_for_timeout(1500)
                cards = page.evaluate(EXTRACT_JS)
                print(f"    encontrados: {len(cards)}")
                for c in cards:
                    items[c["link"]] = {
                        "title": c["title"],
                        "price": int(c["price"]) if c["price"].isdigit() else None,
                        "currency": "ARS",
                        "permalink": c["link"],
                        "thumbnail": c["thumb"] or "",
                        "seller": "—",
                        "confidence": "alta",
                        "signals": ["Envío internacional (filtro de ML)"],
                    }
                if not cards:
                    break

                # Página siguiente
                try:
                    nxt = page.evaluate(
                        "() => { const a = document.querySelector("
                        "\"a[title='Siguiente'], .andes-pagination__button--next a\");"
                        " return a ? a.href : ''; }")
                except Exception:
                    nxt = ""
                url = nxt
                pages += 1
                page.wait_for_timeout(1200)

        ctx.close()

    result = list(items.values())
    result.sort(key=lambda x: (x.get("price") or 1e12))
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "site": "MLA", "mode": "navegador",
        "filter": f"SHIPPING_ORIGIN={INTL_ORIGIN_ID} (internacional)",
        "query_terms": ["bazar-cocina/utensilios"],
        "count": len(result), "items": result,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nOK · {len(result)} artículos -> data.json")
    try:
        gh_put_file("data.json", json.dumps(out, ensure_ascii=False, indent=2).encode(),
                    f"Actualizar resultados {now.date()} (navegador)")
    except Exception as e:
        print(f"  ! No pude subir a GitHub: {e}")


if __name__ == "__main__":
    main()
    if os.name == "nt":
        input("\nListo. Apretá Enter para cerrar…")
