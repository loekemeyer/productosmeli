# Radar Importados — versión para tu PC (Windows, con navegador)

Mercado Libre bloquea la lectura automática incluso desde tu casa cuando se hace
con un programa "pelado". Por eso esta versión usa un **navegador real**
(Playwright) que ML acepta como una persona. Corre en tu PC, lee los importados
de bazar/cocina con envío internacional y **sube el resultado al repo**, así el
panel web **https://loekemeyer.github.io/productosmeli/** se actualiza solo.

No necesita nada de Mercado Libre (ni app, ni CUIT, ni token de ML).

## Instalación (una sola vez)

### 1. Python
Ya lo tenés instalado. (Si no: <https://www.python.org/downloads/>, tildando
**"Add python.exe to PATH"**.)

### 2. Token de GitHub
Ya tenés el token `radar` con **Contents: Read and write**. Tenelo a mano.

### 3. Descargar los archivos
Descargá estos y ponelos **juntos** en una carpeta (ej. `C:\Radar\`), con el
botón de descarga ⤓ ("Download raw file") de cada uno:
- `radar_browser.py`
- `radar-navegador.bat`
- `instalar-navegador.bat`

### 4. Instalar el navegador (una sola vez)
Doble clic en **`instalar-navegador.bat`**. Baja Playwright + un Chrome (~150 MB).
Esperá a que diga "Listo".

### 5. Pegar tu token
Clic derecho en **`radar-navegador.bat`** → *Editar*. Reemplazá
`PEGA_TU_TOKEN_DE_GITHUB_ACA` por tu token. Guardá.

### 6. Probar
Doble clic en **`radar-navegador.bat`**.
- Se abre una ventana de Chrome y navega a Mercado Libre.
- **Si aparece una verificación** ("no soy un robot"), resolvéla ahí en la
  ventana. Queda guardada: las próximas veces no debería volver a pedirla.
- Al terminar, la consola dice `OK · N artículos` y `subido a GitHub`.
- En 1–2 minutos, mirá el panel: <https://loekemeyer.github.io/productosmeli/>

## Que corra solo cada día (Programador de tareas)

1. Abrí **Programador de tareas** (menú Inicio).
2. *Crear tarea básica…* → nombre `Radar Importados`.
3. Desencadenador: **Diariamente** → hora (ej. 09:00).
4. Acción: **Iniciar un programa** → *Examinar* → elegí **`radar-navegador.bat`**.
5. Finalizar. (Corre si la PC está encendida.)

## Personalizar
- **Qué busca**: editá `LISTING_URLS` en `radar_browser.py`. Para otra categoría,
  entrá a ML, filtrá por *Envío internacional* y pegá la URL.

## Si algo no anda
- Si la ventana queda pidiendo verificación y no la podés pasar: avisale a Claude.
- Si dice `0 artículos`: contale a Claude para ajustar los selectores.
