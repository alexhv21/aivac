@echo off
chcp 65001 >nul
cd /d "%~dp0"
call configuracion.bat
if "%BD_CLAVE%"=="CAMBIE_ESTA_CLAVE" (
  echo Abra el archivo configuracion.bat con el Bloc de notas y escriba la contrasena de PostgreSQL en BD_CLAVE.
  pause
  exit /b 1
)
echo Verificando dependencias de Python (la primera vez puede tardar)...
%PY% -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo No se pudieron instalar las dependencias. Verifique su conexion a internet y que Python este instalado.
  pause
  exit /b 1
)
%PY% migrar.py
echo.
echo Iniciando AIVAC en http://127.0.0.1:5000   (cierre esta ventana o presione Ctrl+C para detenerlo)
start "" /b cmd /c "timeout /t 4 >nul & start http://127.0.0.1:5000"
%PY% -m flask --app app run
pause
