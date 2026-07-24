# Radar Importados 🛰️

Agente que revisa **Mercado Libre Argentina** todos los días y arma una lista
de artículos de **bazar y cocina que solo se consiguen por envío internacional**
(productos importados / Cross-Border Trade). Los resultados se muestran en un
**panel web** con nombre, precio, señales de importación y link directo a ML.

Corre solo en **GitHub Actions** (cron diario) — no necesitás dejar tu PC ni
ningún servidor encendido — y publica el panel en **GitHub Pages**.

## Qué hay acá

| Archivo | Para qué |
|---|---|
| `agent.py` | El agente: busca, filtra los importados y genera `data.json`. |
| `index.html` | El panel web que muestra los resultados. |
| `.github/workflows/daily.yml` | La automatización diaria (cron + publicación). |
| `data.json` | Se genera solo en cada corrida. |

## Puesta en marcha (una sola vez, ~5 min)

1. **Creá un repositorio nuevo** en tu cuenta de GitHub (privado o público) y
   subí estos archivos.
2. **Activá GitHub Pages**: en el repo → *Settings → Pages → Build and
   deployment → Source: GitHub Actions*.
3. **Activá los workflows**: pestaña *Actions* → habilitá si te lo pide.
4. **(Recomendado) Token de la API de Mercado Libre** para datos estables:
   - Entrá a <https://developers.mercadolibre.com.ar> con tu cuenta de ML.
   - Creá una aplicación (es gratis) y obtené un *access token*.
   - En el repo → *Settings → Secrets and variables → Actions → New secret*,
     nombre `ML_ACCESS_TOKEN`, valor = tu token.
   - Sin este token, el agente igual funciona en modo *scraping* (más frágil).
5. Andá a *Actions → Radar Importados (diario) → Run workflow* para probarlo ya.
   Cuando termine, tu panel queda en la URL que muestra *Settings → Pages*.

A partir de ahí, corre **solo cada día a las 09:00 (hora Argentina)**.

## Personalizar

- **Qué busca**: editá la lista `QUERY_TERMS` al principio de `agent.py`.
- **Horario**: cambiá el `cron` en `daily.yml` (está en UTC; 12:00 UTC = 09:00 AR).
- **Cuán estricto es**: `MIN_CONFIDENCE` en `agent.py` (`alta`, `media` o `baja`).

## Cómo detecta "solo envío internacional"

Para cada artículo combina varias señales de los datos de ML:

- etiqueta de producto importado / Cross-Border Trade (**CBT**),
- modo de envío internacional activo,
- vendedor con domicilio fuera de Argentina,
- precio en USD.

Con eso asigna un nivel de **confianza**:

- **alta** — coinciden 2+ señales fuertes,
- **media** — 1 señal fuerte o 2 débiles,
- **baja** — candidato a revisar a mano antes de confiar.

> ⚠️ **Importante y honesto:** estas heurísticas son *best-effort*. Mercado Libre
> no expone un único indicador perfecto de "solo importado", y su HTML/API pueden
> cambiar. Conviene mirar los primeros resultados reales y ajustar señales y
> umbrales. Por eso cada ítem lleva su nivel de confianza en vez de afirmar
> certezas. Si usás el modo scraping, revisá los Términos y Condiciones de ML.
