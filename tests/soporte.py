"""Utilidades comunes de las pruebas: conexión a la BD de pruebas y restauración del estado inicial."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

_STOCK_INICIAL = {}


def conn():
    return db.conectar()


def guardar_stock_inicial():
    if _STOCK_INICIAL:
        return  # solo se toma la foto una vez por ejecución (después de cargar los datos demo)
    c = conn(); cur = c.cursor()
    cur.execute("SELECT id_producto, stock_actual FROM producto")
    _STOCK_INICIAL.update({r["id_producto"]: r["stock_actual"] for r in cur.fetchall()})
    c.close()


def restaurar():
    """Deja la BD como después de cargar los datos demo (borra ventas y movimientos, restaura existencias)."""
    c = conn(); cur = c.cursor()
    cur.execute("TRUNCATE detalle_venta, venta, movimiento_inventario, solicitud_refaccion, detalle_orden_servicio, orden_trabajo RESTART IDENTITY CASCADE")
    cur.execute("DELETE FROM producto WHERE codigo LIKE 'TST-%'")
    cur.execute("DELETE FROM vehiculo WHERE placas LIKE 'TST-%'")
    cur.execute("DELETE FROM cliente WHERE nombre LIKE 'TEST %' AND NOT EXISTS (SELECT 1 FROM vehiculo v WHERE v.id_cliente = cliente.id_cliente)")
    for idp, st in _STOCK_INICIAL.items():
        cur.execute("UPDATE producto SET stock_actual = %s WHERE id_producto = %s", (st, idp))
    cur.execute("UPDATE usuario SET activo = TRUE")
    c.commit(); c.close()


def stock(cur, codigo):
    cur.execute("SELECT stock_actual FROM producto WHERE codigo = %s", (codigo,))
    return cur.fetchone()["stock_actual"]
