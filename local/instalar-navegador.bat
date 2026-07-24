@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Instalando Playwright y el navegador (una sola vez).
echo   Puede tardar unos minutos y baja ~150 MB. Espera...
echo ============================================================
echo.

python -m pip install --upgrade pip
python -m pip install playwright
python -m playwright install chromium

echo.
echo ============================================================
echo   Listo. Ya podes usar radar-navegador.bat
echo ============================================================
pause
