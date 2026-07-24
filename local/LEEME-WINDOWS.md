# Radar Importados — versión para tu PC (Windows, con navegador)

Corre en tu PC (tu internet no está bloqueado por ML), acumula día a día los
importados de bazar/cocina con envío internacional, compara cada uno con la
oferta local, y **sube el resultado al repo** para que el panel web se actualice:
**https://loekemeyer.github.io/productosmeli/**

No necesita nada de Mercado Libre (ni app, ni CUIT, ni token de ML).

## Instalación (una sola vez)

### 1. Python
Ya lo tenés. (Si no: <https://www.python.org/downloads/>, tildando *Add to PATH*.)

### 2. Playwright + navegador (una sola vez)
Abrí tu carpeta Radar en el Explorador, clic en la barra de direcciones,
escribí `cmd` y Enter. En esa consola:
```
pip install playwright
python -m playwright install chromium
```

### 3. Token de GitHub
Usá tu token con **Contents: Read and write** sobre `productosmeli`.

### 4. Archivos (en la misma carpeta)
Descargá de la carpeta `local` del repo:
- `radar_browser.py`
- `radar-navegador.bat`
- `no-me-interesa.txt` (opcional)

Pegá tu token dentro de `radar-navegador.bat` (clic derecho → Editar).

### 5. Probar
Doble clic en `radar-navegador.bat` (o desde la consola: `python radar_browser.py`).
Se abre Chrome, escanea, compara y sube. Si pide verificación, resolvéla una vez.

## Que corra solo TODOS LOS DÍAS a las 8:30

1. Abrí **Programador de tareas** (menú Inicio).
2. **Crear tarea básica…** → nombre `Radar Importados` → Siguiente.
3. Desencadenador: **Diariamente** → Siguiente → hora **08:30:00** → Siguiente.
4. Acción: **Iniciar un programa** → *Examinar* → elegí **`radar-navegador.bat`**.
5. Finalizar. (Corre a esa hora si la PC está encendida.)

> Tip: en las propiedades de la tarea podés tildar "Ejecutar aunque el usuario
> no haya iniciado sesión" y "Ejecutar con los privilegios más altos".

## Descartar lo que no te interesa

- **En el panel web** (lo más fácil):
  - Botón **🚫** en cada producto → lo oculta para siempre.
  - Caja **"🚫 Ocultar"** → escribí una palabra (ej. `cosmética`) y Enter: se
    esconde todo lo que la contenga. Se guarda en tu navegador.
- **Permanente y en todos lados** (opcional): editá `no-me-interesa.txt`
  (una palabra por línea). El radar excluye esos productos de raíz en cada corrida.

## Acumulación

El radar recuerda lo de días anteriores y marca lo nuevo como **"Nuevo"**.
Los artículos que no se ven por más de 60 días se van soltando solos para que la
lista no crezca infinito.

## Personalizar
- **Qué busca**: editá `LISTING_URLS` en `radar_browser.py`.
