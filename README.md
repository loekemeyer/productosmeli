# Radar Importados 🛰️

Agente que revisa **Mercado Libre Argentina** todos los días y arma una lista
de artículos de **bazar y cocina que solo se consiguen por envío internacional**
(productos importados / Cross-Border Trade). Los resultados se muestran en un
**panel web** con nombre, precio, señales de importación y link directo a ML.

Corre solo en **GitHub Actions** (cron diario) — no necesitás dejar tu PC ni
ningún servidor encendido — y publica el panel en **GitHub Pages**.

> Usa la **API oficial de Mercado Libre** (vía OAuth). El scraping directo no
> sirve: ML bloquea con captcha a los servidores de nube. La API es gratis.

## Qué hay acá

| Archivo | Para qué |
|---|---|
| `agent.py` | El agente: renueva el token, busca por API y genera `data.json`. |
| `mlauth.py` | OAuth de ML + guardado del refresh token que rota. |
| `setup_token.py` | Canje único del código inicial por el refresh token. |
| `index.html` | El panel web que muestra los resultados. |
| `.github/workflows/daily.yml` | La automatización diaria (cron + publicación). |
| `.github/workflows/setup-token.yml` | Configuración inicial del token (una vez). |
| `data.json` | Se genera solo en cada corrida. |

## Puesta en marcha (una sola vez)

### 1. Crear la app en Mercado Libre (gratis)
1. Entrá a <https://developers.mercadolibre.com.ar> → *Mis aplicaciones* →
   *Crear aplicación*.
2. En **Redirect URI** poné exactamente:
   `https://loekemeyer.github.io/productosmeli/`
3. Guardá y anotá el **App ID** (client id) y la **Clave secreta** (client secret).

### 2. Crear un token de GitHub (para que el robot guarde su propio token)
1. <https://github.com/settings/personal-access-tokens/new> (fine-grained).
2. *Repository access* → *Only select repositories* → `productosmeli`.
3. *Permissions* → *Repository permissions* → **Secrets: Read and write**.
4. Generá y copiá el token (empieza con `github_pat_...`).

### 3. Cargar los secretos en el repo
En el repo → *Settings → Secrets and variables → Actions → New repository secret*.
Creá estos tres:

| Nombre | Valor |
|---|---|
| `ML_CLIENT_ID` | el App ID de tu app de ML |
| `ML_CLIENT_SECRET` | la clave secreta de tu app de ML |
| `GH_PAT` | el token de GitHub del paso 2 |

### 4. Autorizar (obtener el código)
1. Abrí esta URL en el navegador (reemplazá `TU_APP_ID`):
   `https://auth.mercadolibre.com.ar/authorization?response_type=code&client_id=TU_APP_ID&redirect_uri=https://loekemeyer.github.io/productosmeli/`
2. Iniciá sesión y autorizá. El navegador te lleva a tu página con
   `?code=TG-xxxxxxxx` en la barra de direcciones. **Copiá ese valor** (lo que
   sigue a `code=`).

### 5. Ejecutar la configuración inicial
1. Pestaña *Actions* → **Configurar token (una sola vez)** → *Run workflow*.
2. Pegá el **code** del paso 4 y dejá la Redirect URI por defecto → *Run*.
3. Cuando termine, el refresh token queda guardado solo.

### 6. ¡Listo!
Andá a *Actions → Radar Importados (diario) → Run workflow* para probarlo ya.
El panel queda en:

**https://loekemeyer.github.io/productosmeli/**

A partir de ahí corre **solo cada día a las 09:00 (hora Argentina)** y el token
se renueva automáticamente.

## Personalizar

- **Qué busca**: editá la lista `QUERY_TERMS` en `agent.py`.
- **Horario**: cambiá el `cron` en `daily.yml` (está en UTC; 12:00 UTC = 09:00 AR).

## Cómo detecta "solo envío internacional"

Usa el **propio filtro de Mercado Libre**: el parámetro de origen de envío
internacional (`shipping_origin=10215069`). Todo lo que aparece con ese filtro
es, por construcción, de envío internacional. A cada artículo le suma señales de
detalle (país del vendedor, precio en USD).

> ⚠️ **Nota honesta:** las heurísticas exactas y el parámetro del filtro se
> validan con datos reales en la primera corrida con token; puede requerir un
> pequeño ajuste. Cada artículo lleva su nivel de confianza.
