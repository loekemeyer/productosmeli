# Radar Importados 🛰️

Arma una lista de artículos de **bazar y cocina de Mercado Libre Argentina que
solo se consiguen por envío internacional** (importados), y la muestra en un
**panel web**: **https://loekemeyer.github.io/productosmeli/**

## Cómo funciona

Mercado Libre bloquea la lectura automática desde servidores de nube (captcha) y
tiene restringida su API de búsqueda para terceros. Por eso el radar corre en
**tu PC** —desde tu conexión de casa, que no está bloqueada— y **sube los
resultados a este repositorio**; entonces el panel web se publica solo.

```
Tu PC (radar.py)  ──lee ML──►  data.json  ──sube al repo──►  GitHub Pages (panel)
```

## Puesta en marcha

Seguí la guía para Windows: **[`local/LEEME-WINDOWS.md`](local/LEEME-WINDOWS.md)**

Resumen: instalar Python, poner un token de GitHub en `radar.bat`, y programar
`radar.bat` con el Programador de tareas para que corra solo cada día.

## Qué hay acá

| Archivo | Para qué |
|---|---|
| `local/radar.py` | El programa que corre en tu PC: lee ML y sube `data.json`. |
| `local/radar.bat` | Lanzador para Windows (ahí va tu token de GitHub). |
| `local/LEEME-WINDOWS.md` | Guía de instalación paso a paso. |
| `index.html` | El panel web que muestra los resultados. |
| `data.json` | Los resultados (lo actualiza tu PC). |
| `.github/workflows/daily.yml` | Publica el panel cada vez que se sube `data.json`. |

## Detecta "solo envío internacional"

Usa el **propio filtro de Mercado Libre** (`SHIPPING_ORIGIN=10215069`): lee las
páginas de listado ya filtradas por envío internacional, así que todo lo que
aparece es importado por construcción.
