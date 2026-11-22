@echo off
chcp 65001 >nul
cd /d "%~dp0"
call configuracion.bat
%PY% -m pip install -q -r requirements.txt
echo Cargando datos de ejemplo (si la base ya tiene datos, no hace nada)...
%PY% migrar.py
%PY% seed_demo.py
pause
