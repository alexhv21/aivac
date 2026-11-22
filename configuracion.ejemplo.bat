@echo off
rem ============================================================
rem  CONFIGURACION DE AIVAC  -  edite solo estas lineas
rem  Evite los caracteres % ^ & ! en la contrasena dentro de este archivo.
rem ============================================================
set "BD_NOMBRE=aivac"
set "BD_USUARIO=postgres"
set "BD_CLAVE=CAMBIE_ESTA_CLAVE"
set "BD_HOST=localhost"
set "BD_PUERTO=5432"
rem Clave que protege las sesiones del navegador (cualquier texto largo)
set "AIVAC_SECRET=aivac-clave-2026"

set "AIVAC_DSN=dbname=%BD_NOMBRE% user=%BD_USUARIO% password=%BD_CLAVE% host=%BD_HOST% port=%BD_PUERTO%"

rem Busca Python: primero el lanzador "py", si no existe usa "python"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py") else (set "PY=python")
