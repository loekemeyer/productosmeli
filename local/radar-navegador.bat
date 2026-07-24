@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ============================================================
REM   Radar Importados (navegador) - lanzador para Windows
REM   Pega tu token de GitHub (Contents: Read and write) abajo.
REM ============================================================

set GH_TOKEN=PEGA_TU_TOKEN_DE_GITHUB_ACA
set GH_REPO=loekemeyer/productosmeli

python radar_browser.py
