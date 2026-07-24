@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ============================================================
REM   Radar Importados - lanzador para Windows
REM   Pega tu token de GitHub entre las comillas de abajo.
REM   (El token debe tener permiso "Contents: Read and write")
REM ============================================================

set GH_TOKEN=PEGA_TU_TOKEN_DE_GITHUB_ACA
set GH_REPO=loekemeyer/productosmeli

python radar.py
