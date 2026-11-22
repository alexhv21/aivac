"""Lógica de negocio del módulo de ventas (HU-02, HU-03, HU-04 y HU-08).

Reglas principales (apartados 3.4.4 y 3.4.5 del reporte):
  * Una venta contiene una o más partidas; cada partida es una refacción O un servicio.
  * El precio de cada partida se toma SIEMPRE de la base de datos, nunca de lo que
    envía el navegador (evita alteraciones del importe).
  * Las refacciones vendidas generan un movimiento de inventario de tipo «salida»;
    el disparador trg_movimiento_stock descuenta el stock de forma automática (RF-08).
  * Toda la operación se ejecuta en una sola transacción (RNF-07).
"""
from decimal import Decimal

FORMAS_PAGO = ("efectivo", "tarjeta", "transferencia", "credito")


class VentaError(Exception):
    """Error de validación o de regla de negocio; su mensaje se muestra al usuario."""


# ----------------------------------------------------------------------------- consultas
def buscar_catalogo(cur, texto, limite=15):
    """Busca refacciones y servicios por nombre o código (HU-02).

    Devuelve una lista de diccionarios con: tipo ('producto' o 'servicio'), id, codigo,
    nombre, precio y existencia (None para servicios, que no manejan inventario).
    """
    patron = "%" + texto.strip() + "%"
    cur.execute(
        """SELECT 'producto' AS tipo, id_producto AS id, codigo, nombre, marca,
                  precio_venta AS precio, stock_actual AS existencia
             FROM producto
            WHERE nombre ILIKE %s OR codigo ILIKE %s
            ORDER BY nombre LIMIT %s""", (patron, patron, limite))
    productos = cur.fetchall()
    cur.execute(
        """SELECT 'servicio' AS tipo, id_servicio AS id, '' AS codigo, nombre, NULL AS marca,
                  precio_base AS precio, NULL AS existencia
             FROM servicio WHERE nombre ILIKE %s ORDER BY nombre LIMIT %s""", (patron, limite))
    return list(productos) + list(cur.fetchall())


def buscar_clientes(cur, texto, limite=10):
    """Busca clientes por nombre, teléfono o placas de alguno de sus vehículos."""
    patron = "%" + texto.strip() + "%"
    cur.execute(
        """SELECT DISTINCT c.id_cliente, c.nombre, c.tipo_cliente, c.telefono
             FROM cliente c LEFT JOIN vehiculo v ON v.id_cliente = c.id_cliente
            WHERE c.nombre ILIKE %s OR c.telefono ILIKE %s OR v.placas ILIKE %s
            ORDER BY c.nombre LIMIT %s""", (patron, patron, patron, limite))
    return cur.fetchall()


def inventario(cur):
    """Existencias con su estatus: suficiente, próximo al mínimo, reabastecer o sin existencia."""
    cur.execute("""SELECT codigo, nombre, stock_actual, stock_minimo,
                          CASE WHEN stock_actual = 0 THEN 'sin existencia'
                               WHEN stock_actual <= stock_minimo THEN 'reabastecer'
                               WHEN stock_actual <= stock_minimo * 1.5 THEN 'próximo al mínimo'
                               ELSE 'suficiente' END AS estatus
                     FROM producto ORDER BY nombre""")
    return cur.fetchall()


# ----------------------------------------------------------------------------- registro
def _validar_partidas(partidas):
    """Normaliza y valida las partidas recibidas; lanza VentaError si algo es inválido."""
    if not partidas:
        raise VentaError("Agregue al menos una refacción o servicio a la venta.")
    limpias = []
    for p in partidas:
        try:
            cantidad = int(p.get("cantidad", 0))
            ident = int(p.get("id"))
        except (TypeError, ValueError):
            raise VentaError("Una de las partidas tiene datos inválidos.")
        if p.get("tipo") not in ("producto", "servicio"):
            raise VentaError("El tipo de partida debe ser producto o servicio.")
        if cantidad <= 0:
            raise VentaError("La cantidad de cada partida debe ser mayor que cero.")
        limpias.append({"tipo": p["tipo"], "id": ident, "cantidad": cantidad})
    return limpias


def _dinero(valor, nombre):
    """Convierte a Decimal con dos decimales un importe recibido del navegador."""
    try:
        d = Decimal(str(valor).replace("$", "").replace(",", "").strip())
    except Exception:
        raise VentaError("%s no es un importe válido." % nombre)
    if d < 0 or d > Decimal("9999999.99"):
        raise VentaError("%s no es un importe válido." % nombre)
    return d.quantize(Decimal("0.01"))


def registrar_venta(conn, id_usuario, id_cliente, forma_pago, partidas, monto_recibido=None):
    """Registra una venta completa (HU-02, HU-03, HU-08) y devuelve su identificador.

    Pasos, todos dentro de la misma transacción:
      1. Valida forma de pago y partidas.
      2. Inserta el encabezado en `venta`.
      3. Por cada partida: obtiene el precio vigente, verifica la existencia (bloqueando
         la fila con FOR UPDATE para evitar ventas simultáneas del mismo producto),
         inserta en `detalle_venta` y, si es refacción, registra la salida en
         `movimiento_inventario` (el disparador descuenta el stock).
      4. Si el pago es en efectivo y se indica el monto recibido, verifica que cubra el total y
         guarda el cambio que debe entregarse (se imprime en el comprobante).
    Si cualquier paso falla se hace rollback y no queda ningún dato parcial.
    """
    if forma_pago not in FORMAS_PAGO:
        raise VentaError("Seleccione una forma de pago válida (efectivo, tarjeta, transferencia o crédito).")
    partidas = _validar_partidas(partidas)
    if forma_pago == "efectivo" and monto_recibido not in (None, ""):
        monto_recibido = _dinero(monto_recibido, "El efectivo recibido")
    else:
        monto_recibido = None
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO venta (id_cliente, id_usuario, forma_pago) VALUES (%s, %s, %s) RETURNING id_venta",
                    (id_cliente, id_usuario, forma_pago))
        id_venta = cur.fetchone()["id_venta"]
        for p in partidas:
            if p["tipo"] == "producto":
                cur.execute("SELECT nombre, precio_venta, stock_actual FROM producto WHERE id_producto = %s FOR UPDATE", (p["id"],))
                fila = cur.fetchone()
                if fila is None:
                    raise VentaError("La refacción seleccionada ya no existe en el catálogo.")
                if fila["stock_actual"] < p["cantidad"]:
                    raise VentaError("Sin existencia suficiente de «%s»: disponible %d, solicitado %d."
                                     % (fila["nombre"], fila["stock_actual"], p["cantidad"]))
                cur.execute("""INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario)
                               VALUES (%s, %s, %s, %s)""", (id_venta, p["id"], p["cantidad"], fila["precio_venta"]))
                cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, referencia)
                               VALUES (%s, %s, 'salida', %s, %s)""", (p["id"], id_usuario, p["cantidad"], "VENTA-%d" % id_venta))
            else:
                cur.execute("SELECT precio_base FROM servicio WHERE id_servicio = %s", (p["id"],))
                fila = cur.fetchone()
                if fila is None:
                    raise VentaError("El servicio seleccionado ya no existe en el catálogo.")
                cur.execute("""INSERT INTO detalle_venta (id_venta, id_servicio, cantidad, precio_unitario)
                               VALUES (%s, %s, %s, %s)""", (id_venta, p["id"], p["cantidad"], fila["precio_base"]))
        if monto_recibido is not None:
            cur.execute("SELECT total FROM v_venta_total WHERE id_venta = %s", (id_venta,))
            total = cur.fetchone()["total"]
            if monto_recibido < total:
                raise VentaError("El efectivo recibido ($%s) no cubre el total de la venta ($%s)."
                                 % ("{:,.2f}".format(monto_recibido), "{:,.2f}".format(total)))
            cur.execute("UPDATE venta SET monto_recibido = %s, cambio = %s WHERE id_venta = %s",
                        (monto_recibido, monto_recibido - total, id_venta))
        conn.commit()
        return id_venta
    except Exception:
        conn.rollback()
        raise


def comprobante(cur, id_venta):
    """Devuelve (encabezado, partidas, total) del comprobante interno de una venta (HU-04)."""
    cur.execute("""SELECT v.id_venta, v.fecha, v.forma_pago, t.total, v.monto_recibido, v.cambio,
                          COALESCE(c.nombre, 'Venta de mostrador') AS cliente, u.nombre_completo AS atendio
                     FROM venta v
                     JOIN v_venta_total t ON t.id_venta = v.id_venta
                     JOIN usuario u ON u.id_usuario = v.id_usuario
                     LEFT JOIN cliente c ON c.id_cliente = v.id_cliente
                    WHERE v.id_venta = %s""", (id_venta,))
    cab = cur.fetchone()
    if cab is None:
        return None, [], Decimal(0)
    cur.execute("""SELECT COALESCE(p.nombre, s.nombre) AS concepto, d.cantidad, d.precio_unitario, d.subtotal
                     FROM v_detalle_venta d
                     LEFT JOIN producto p ON p.id_producto = d.id_producto
                     LEFT JOIN servicio s ON s.id_servicio = d.id_servicio
                    WHERE d.id_venta = %s ORDER BY d.id_detalle""", (id_venta,))
    return cab, cur.fetchall(), cab["total"]


def ventas_recientes(cur, limite=10):
    """Últimas ventas registradas con su total (para el historial)."""
    cur.execute("""SELECT t.id_venta, t.fecha, t.forma_pago, t.total, COALESCE(c.nombre, 'Mostrador') AS cliente
                     FROM v_venta_total t LEFT JOIN cliente c ON c.id_cliente = t.id_cliente
                    ORDER BY t.id_venta DESC LIMIT %s""", (limite,))
    return cur.fetchall()
