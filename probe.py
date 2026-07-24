#!/usr/bin/env python3
"""Sonda de diagnóstico: prueba qué acepta la API/So web de ML desde el runner.
No forma parte del agente; solo sirve para decidir la estrategia de acceso."""
import os
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
TOKEN = os.environ.get("ML_ACCESS_TOKEN", "").strip()


def probe(name, url, headers):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(400).decode("utf-8", "replace")
            print(f"[{name}] HTTP {r.status} · {url}")
            print("   ", body.replace("\n", " ")[:300])
    except urllib.error.HTTPError as e:
        body = e.read(400).decode("utf-8", "replace") if e.fp else ""
        print(f"[{name}] HTTP {e.code} (error) · {url}")
        print("   ", body.replace("\n", " ")[:300])
    except Exception as e:
        print(f"[{name}] EXCEPCIÓN {type(e).__name__}: {e}")


base = {"User-Agent": UA, "Accept-Language": "es-AR,es;q=0.9"}
print("=== SONDA MERCADO LIBRE ===  token:", "sí" if TOKEN else "no")
probe("api-sin-token", "https://api.mercadolibre.com/sites/MLA/search?q=pelador&limit=1", base)
if TOKEN:
    h = dict(base); h["Authorization"] = f"Bearer {TOKEN}"
    probe("api-con-token",
          "https://api.mercadolibre.com/sites/MLA/search?q=pelador&limit=1&shipping_origin=10215069", h)
probe("api-categorias", "https://api.mercadolibre.com/sites/MLA/categories", base)
