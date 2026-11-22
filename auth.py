"""Autenticación y control de acceso por rol (HU-01, RF-27, RF-28, RNF-04, RNF-05)."""
from functools import wraps

from flask import abort, redirect, session, url_for
from werkzeug.security import check_password_hash

# Roles autorizados por módulo (RF-28)
ROLES_VENTAS = ("Gerente Administrativa", "Jefe de Refaccionaria")
ROLES_INVENTARIO = ("Gerente Principal", "Gerente Administrativa", "Jefe de Refaccionaria")
ROLES_CLIENTES = ("Gerente Principal", "Gerente Administrativa", "Jefe de Refaccionaria")
# Órdenes de trabajo: el mecánico solo ve y trabaja las órdenes que se le asignaron
ROLES_ORDENES = ("Gerente Principal", "Gerente Administrativa", "Jefe de Refaccionaria", "Mecánico")


def autenticar(cur, nombre_usuario, contrasena):
    """Devuelve el usuario (dict con rol) si las credenciales son válidas y está activo; si no, None.

    La contraseña nunca se guarda en texto plano: se compara contra un hash con sal.
    """
    cur.execute("""SELECT u.id_usuario, u.nombre_completo, u.contrasena_hash, r.nombre AS rol
                     FROM usuario u JOIN rol r ON r.id_rol = u.id_rol
                    WHERE u.nombre_usuario = %s AND u.activo""", (nombre_usuario,))
    u = cur.fetchone()
    if u and check_password_hash(u["contrasena_hash"], contrasena):
        return u
    return None


def rol_requerido(*roles):
    """Decorador de rutas: exige sesión iniciada (302 a /login) y rol autorizado (403)."""
    def deco(vista):
        @wraps(vista)
        def envoltura(*a, **kw):
            if "id_usuario" not in session:
                return redirect(url_for("login"))
            if session.get("rol") not in roles:
                abort(403)
            return vista(*a, **kw)
        return envoltura
    return deco
