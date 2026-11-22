# AIVAC – Sistema Integral de Ventas y Almacén Castellanos

Proyecto integrador del **Equipo 1**, Gestión de Proyectos de Software (8SB), Instituto Tecnológico de Oaxaca.
Aplicación web (Flask + PostgreSQL) para el Taller de Alineación y Balanceo Castellanos: ventas, inventario de refacciones, clientes, vehículos y órdenes de trabajo, con acceso por rol.

> Los datos de ejemplo son **ficticios**. Antes de usar el sistema con datos reales, cambien las contraseñas de los usuarios de ejemplo.

## Requisitos
- Python 3.10 o superior
- PostgreSQL 14 o superior (con pgAdmin)

## Puesta en marcha (Windows)
1. En pgAdmin cree la base `aivac` y ejecute `db/aivac_schema.sql` (clic derecho en la base → Query Tool → abrir archivo → Play).
2. **Copie** `configuracion.ejemplo.bat` como `configuracion.bat` y escriba su contraseña de PostgreSQL en `BD_CLAVE`. Ese archivo está en `.gitignore`: **no se sube a GitHub**, así cada integrante usa su propia contraseña.
3. Doble clic en `cargar_datos.bat` (una sola vez) para cargar datos de ejemplo.
4. Doble clic en `iniciar.bat` → se abre en http://127.0.0.1:5000

Usuarios de ejemplo (contraseña `Demo2026!`): `gerente.admin`, `refacciones`, `gerente.principal`, `mecanico1`, `mecanico2`, `mecanico3`, `repartidor`.

Más detalles (importar el catálogo real, pruebas) en `LEEME.txt`.

## Pruebas automáticas
Usen una base aparte (por ejemplo `aivac_test`); las pruebas borran ventas, órdenes y movimientos.
```
set "AIVAC_DSN=dbname=aivac_test user=postgres password=SU_CLAVE host=localhost port=5432"
py -m unittest tests.test_ventas tests.test_app tests.test_taller tests.test_app_taller tests.test_cambio_catalogo
```

## Trabajo en equipo con Git
```
git clone <URL-del-repositorio>
git checkout -b mi-cambio      # trabajar en una rama
git add . && git commit -m "Descripción del cambio"
git push -u origin mi-cambio   # y abrir un Pull Request en GitHub
```
