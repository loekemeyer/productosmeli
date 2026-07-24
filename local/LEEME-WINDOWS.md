# Radar Importados — versión para tu PC (Windows)

Esta versión corre en **tu computadora** (tu internet de casa, donde Mercado
Libre no bloquea) y **sube los resultados al repositorio**, así el panel web
**https://loekemeyer.github.io/productosmeli/** se actualiza solo.

No necesita cuenta de desarrollador, ni CUIT, ni token de Mercado Libre.

## Instalación (una sola vez)

### 1. Instalar Python
- Bajalo de <https://www.python.org/downloads/>
- Al instalarlo, **tildá la casilla "Add python.exe to PATH"** (abajo del instalador).
- Terminá la instalación.

### 2. Token de GitHub (con permiso de escritura)
Necesitás un token con permiso **Contents: Read and write**.
- Andá a <https://github.com/settings/personal-access-tokens>
- Editá el token `radar` que ya creaste (o creá uno nuevo) y en
  *Permissions → Repository permissions* agregá **Contents → Read and write**.
- Copiá el token (`github_pat_...`). Si lo regenerás, usá el valor nuevo.

### 3. Descargar los archivos
- Descargá **`radar.py`** y **`radar.bat`** (esta carpeta `local` del repo) y
  ponelos juntos en una carpeta, por ejemplo `C:\Radar\`.
  (En GitHub: entrá a cada archivo → botón *Download raw file*.)

### 4. Pegar tu token
- Abrí **`radar.bat`** con el Bloc de notas (clic derecho → *Editar*).
- Reemplazá `PEGA_TU_TOKEN_DE_GITHUB_ACA` por tu token. Guardá.

### 5. Probar
- Hacé **doble clic en `radar.bat`**.
- Debería decir cuántos artículos encontró y "subido a GitHub".
- En 1–2 minutos, mirá el panel: <https://loekemeyer.github.io/productosmeli/>

## Que corra solo cada día (Programador de tareas)

1. Abrí **Programador de tareas** (buscalo en el menú Inicio).
2. *Crear tarea básica…* → nombre: `Radar Importados`.
3. Desencadenador: **Diariamente** → elegí la hora (ej. 09:00).
4. Acción: **Iniciar un programa** → *Examinar* → elegí tu `radar.bat`.
5. Finalizar. Listo: corre solo a esa hora (si la PC está encendida).

## Personalizar
- **Qué busca**: editá la lista `LISTING_URLS` en `radar.py`. Para agregar otra
  categoría, entrá a ML, filtrá por *Envío internacional* y pegá la URL.

## Si algo no anda
- Si dice **0 artículos** o **captcha**: el programa sube un archivo
  `debug_page.html` al repo. Avisale a Claude y con eso ajusta el lector.
- Si dice que no encuentra `python`: reinstalá Python tildando *Add to PATH*.
