"""Lógica de negocio del taller: clientes, vehículos y órdenes de trabajo (Sprint 3).

Cada función que modifica datos recibe la conexión, confirma (commit) al terminar bien y
hace rollback si algo falla, de modo que nunca queda información a medias.
Los errores de validación se reportan con TallerError, con un mensaje apto para el usuario.
"""
import re

TIPOS_CLIENTE = ("particular", "flotilla", "taller")
TIPOS_USO = ("particular", "reparto")
ESTATUS_ORDEN = ("abierta", "en_proceso", "terminada", "entregada", "cancelada")
ETIQUETA_ESTATUS = {"abierta": "Abierta", "en_proceso": "En proceso", "terminada": "Terminada",
                    "entregada": "Entregada", "cancelada": "Cancelada"}
# Estatus siguiente permitido desde cada estatus (la orden avanza en un solo sentido)
TRANSICIONES = {"abierta": ("en_proceso", "cancelada"), "en_proceso": ("terminada", "cancelada"),
                "terminada": ("entregada",), "entregada": (), "cancelada": ()}
EDITABLES = ("abierta", "en_proceso")  # estatus en los que aún se pueden agregar conceptos


class TallerError(Exception):
    """Error de validación o de regla de negocio con mensaje para el usuario."""


def _texto(valor, nombre, obligatorio=False, maximo=100):
    valor = (valor or "").strip()
    if obligatorio and not valor:
        raise TallerError("%s es obligatorio." % nombre)
    if len(valor) > maximo:
        raise TallerError("%s no puede tener más de %d caracteres." % (nombre, maximo))
    return valor or None


def _entero(valor, nombre, minimo, maximo=None, obligatorio=True):
    if valor in (None, ""):
        if obligatorio:
            raise TallerError("%s es obligatorio." % nombre)
        return None
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise TallerError("%s debe ser un número entero." % nombre)
    if n < minimo or (maximo is not None and n > maximo):
        raise TallerError("%s debe estar entre %d y %s." % (nombre, minimo, maximo if maximo is not None else "el máximo permitido"))
    return n


# --------------------------------------------------------------------------- clientes
def listar_clientes(cur, texto=""):
    """Clientes con su número de vehículos, filtrados por nombre o teléfono."""
    cur.execute("""SELECT c.id_cliente, c.nombre, c.tipo_cliente, c.telefono, c.correo,
                          COUNT(v.id_vehiculo) AS vehiculos
                     FROM cliente c LEFT JOIN vehiculo v ON v.id_cliente = c.id_cliente
                    WHERE c.nombre ILIKE %s OR COALESCE(c.telefono, '') LIKE %s
                    GROUP BY c.id_cliente ORDER BY c.nombre""", ("%" + texto.strip() + "%", "%" + texto.strip() + "%"))
    return cur.fetchall()


def obtener_cliente(cur, id_cliente):
    cur.execute("SELECT * FROM cliente WHERE id_cliente = %s", (id_cliente,))
    return cur.fetchone()


def guardar_cliente(conn, datos, id_cliente=None):
    """Crea (id_cliente=None) o actualiza un cliente y devuelve su id."""
    nombre = _texto(datos.get("nombre"), "El nombre", True)
    tipo = datos.get("tipo_cliente")
    if tipo not in TIPOS_CLIENTE:
        raise TallerError("Seleccione un tipo de cliente válido (particular, flotilla o taller).")
    telefono = _texto(datos.get("telefono"), "El teléfono", maximo=15)
    if telefono and not re.fullmatch(r"\d{10}", re.sub(r"[\s\-()]", "", telefono)):
        raise TallerError("El teléfono debe tener 10 dígitos.")
    if telefono:
        telefono = re.sub(r"[\s\-()]", "", telefono)
    correo = _texto(datos.get("correo"), "El correo")
    if correo and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
        raise TallerError("El correo no tiene un formato válido.")
    acepta = bool(datos.get("acepta_notificaciones"))
    cur = conn.cursor()
    try:
        if id_cliente is None:
            cur.execute("""INSERT INTO cliente (nombre, tipo_cliente, telefono, correo, acepta_notificaciones)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id_cliente""", (nombre, tipo, telefono, correo, acepta))
            id_cliente = cur.fetchone()["id_cliente"]
        else:
            cur.execute("""UPDATE cliente SET nombre=%s, tipo_cliente=%s, telefono=%s, correo=%s, acepta_notificaciones=%s
                            WHERE id_cliente=%s""", (nombre, tipo, telefono, correo, acepta, id_cliente))
            if cur.rowcount == 0:
                raise TallerError("El cliente no existe.")
        conn.commit()
        return id_cliente
    except Exception:
        conn.rollback()
        raise


# --------------------------------------------------------------------------- vehículos
def listar_vehiculos(cur, texto="", id_cliente=None):
    cur.execute("""SELECT v.*, c.nombre AS cliente
                     FROM vehiculo v JOIN cliente c ON c.id_cliente = v.id_cliente
                    WHERE (v.placas ILIKE %s OR COALESCE(v.marca,'') ILIKE %s OR COALESCE(v.modelo,'') ILIKE %s OR c.nombre ILIKE %s)
                      AND (%s::int IS NULL OR v.id_cliente = %s::int)
                    ORDER BY v.placas""", (("%" + texto.strip() + "%",) * 4) + (id_cliente, id_cliente))
    return cur.fetchall()


def obtener_vehiculo(cur, id_vehiculo):
    cur.execute("""SELECT v.*, c.nombre AS cliente FROM vehiculo v JOIN cliente c ON c.id_cliente = v.id_cliente
                    WHERE v.id_vehiculo = %s""", (id_vehiculo,))
    return cur.fetchone()


def guardar_vehiculo(conn, datos, id_vehiculo=None):
    """Crea o actualiza un vehículo. Las placas son únicas y se guardan en mayúsculas."""
    id_cliente = _entero(datos.get("id_cliente"), "El cliente", 1)
    placas = _texto(datos.get("placas"), "Las placas", True, 10).upper().replace(" ", "")
    marca = _texto(datos.get("marca"), "La marca", maximo=30)
    modelo = _texto(datos.get("modelo"), "El modelo", maximo=40)
    anio = _entero(datos.get("anio"), "El año", 1950, 2100, obligatorio=False)
    uso = datos.get("tipo_uso") or "particular"
    if uso not in TIPOS_USO:
        raise TallerError("Seleccione un tipo de uso válido (particular o reparto).")
    km = _entero(datos.get("kilometraje_actual") or 0, "El kilometraje", 0, 3000000)
    cur = conn.cursor()
    try:
        if obtener_cliente(cur, id_cliente) is None:
            raise TallerError("El cliente seleccionado no existe.")
        cur.execute("SELECT id_vehiculo FROM vehiculo WHERE placas = %s", (placas,))
        otro = cur.fetchone()
        if otro and otro["id_vehiculo"] != id_vehiculo:
            raise TallerError("Ya existe un vehículo con las placas %s." % placas)
        if id_vehiculo is None:
            cur.execute("""INSERT INTO vehiculo (id_cliente, placas, marca, modelo, anio, tipo_uso, kilometraje_actual)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id_vehiculo""", (id_cliente, placas, marca, modelo, anio, uso, km))
            id_vehiculo = cur.fetchone()["id_vehiculo"]
        else:
            cur.execute("""UPDATE vehiculo SET id_cliente=%s, placas=%s, marca=%s, modelo=%s, anio=%s, tipo_uso=%s,
                                  kilometraje_actual=%s WHERE id_vehiculo=%s""",
                        (id_cliente, placas, marca, modelo, anio, uso, km, id_vehiculo))
            if cur.rowcount == 0:
                raise TallerError("El vehículo no existe.")
        conn.commit()
        return id_vehiculo
    except Exception:
        conn.rollback()
        raise


# --------------------------------------------------------------------------- órdenes de trabajo
def mecanicos(cur):
    cur.execute("""SELECT u.id_usuario, u.nombre_completo FROM usuario u JOIN rol r ON r.id_rol = u.id_rol
                    WHERE r.nombre = 'Mecánico' AND u.activo ORDER BY u.nombre_completo""")
    return cur.fetchall()


def listar_ordenes(cur, estatus=None, id_mecanico=None):
    cur.execute("""SELECT o.id_orden, o.fecha_ingreso, o.estatus, v.placas, v.marca, v.modelo, c.nombre AS cliente,
                          m.nombre_completo AS mecanico,
                          COALESCE((SELECT SUM(d.precio_aplicado) FROM detalle_orden_servicio d WHERE d.id_orden = o.id_orden), 0)
                        + COALESCE((SELECT SUM(s.cantidad * p.precio_venta) FROM solicitud_refaccion s
                                      JOIN producto p ON p.id_producto = s.id_producto
                                     WHERE s.id_orden = o.id_orden AND s.estatus = 'surtida'), 0) AS total
                     FROM orden_trabajo o JOIN vehiculo v ON v.id_vehiculo = o.id_vehiculo
                     JOIN cliente c ON c.id_cliente = v.id_cliente JOIN usuario m ON m.id_usuario = o.id_mecanico
                    WHERE (%s::text IS NULL OR o.estatus = %s::text) AND (%s::int IS NULL OR o.id_mecanico = %s::int)
                    ORDER BY o.fecha_ingreso DESC, o.id_orden DESC LIMIT 200""", (estatus, estatus, id_mecanico, id_mecanico))
    return cur.fetchall()


def crear_orden(conn, id_vehiculo, id_mecanico, kilometraje, observaciones=""):
    """Abre una orden de trabajo para un vehículo y devuelve su id."""
    id_vehiculo = _entero(id_vehiculo, "El vehículo", 1)
    id_mecanico = _entero(id_mecanico, "El mecánico", 1)
    km = _entero(kilometraje, "El kilometraje de ingreso", 0, 3000000)
    obs = _texto(observaciones, "Las observaciones", maximo=1000)
    cur = conn.cursor()
    try:
        veh = obtener_vehiculo(cur, id_vehiculo)
        if veh is None:
            raise TallerError("El vehículo seleccionado no existe.")
        if km < veh["kilometraje_actual"]:
            raise TallerError("El kilometraje de ingreso (%d) no puede ser menor al último registrado (%d)." % (km, veh["kilometraje_actual"]))
        cur.execute("""SELECT 1 FROM usuario u JOIN rol r ON r.id_rol = u.id_rol
                        WHERE u.id_usuario = %s AND r.nombre = 'Mecánico' AND u.activo""", (id_mecanico,))
        if cur.fetchone() is None:
            raise TallerError("Seleccione un mecánico activo.")
        cur.execute("""SELECT id_orden FROM orden_trabajo WHERE id_vehiculo = %s AND estatus IN ('abierta','en_proceso')""", (id_vehiculo,))
        abierta = cur.fetchone()
        if abierta:
            raise TallerError("El vehículo ya tiene la orden abierta OT-%05d; ciérrela o cancélela antes de abrir otra." % abierta["id_orden"])
        cur.execute("""INSERT INTO orden_trabajo (id_vehiculo, id_mecanico, kilometraje_ingreso, observaciones)
                       VALUES (%s,%s,%s,%s) RETURNING id_orden""", (id_vehiculo, id_mecanico, km, obs))
        id_orden = cur.fetchone()["id_orden"]
        conn.commit()
        return id_orden
    except Exception:
        conn.rollback()
        raise


def obtener_orden(cur, id_orden):
    """Devuelve (encabezado, servicios, refacciones, total) o (None, [], [], 0)."""
    cur.execute("""SELECT o.*, v.placas, v.marca, v.modelo, v.anio, v.id_cliente, c.nombre AS cliente, c.telefono,
                          m.nombre_completo AS mecanico
                     FROM orden_trabajo o JOIN vehiculo v ON v.id_vehiculo = o.id_vehiculo
                     JOIN cliente c ON c.id_cliente = v.id_cliente JOIN usuario m ON m.id_usuario = o.id_mecanico
                    WHERE o.id_orden = %s""", (id_orden,))
    cab = cur.fetchone()
    if cab is None:
        return None, [], [], 0
    cur.execute("""SELECT s.id_servicio, s.nombre, d.precio_aplicado FROM detalle_orden_servicio d
                     JOIN servicio s ON s.id_servicio = d.id_servicio WHERE d.id_orden = %s ORDER BY s.nombre""", (id_orden,))
    servicios = cur.fetchall()
    cur.execute("""SELECT r.id_solicitud, p.codigo, p.nombre, r.cantidad, r.estatus, p.precio_venta,
                          r.cantidad * p.precio_venta AS importe
                     FROM solicitud_refaccion r JOIN producto p ON p.id_producto = r.id_producto
                    WHERE r.id_orden = %s ORDER BY r.id_solicitud""", (id_orden,))
    refacciones = cur.fetchall()
    total = sum(s["precio_aplicado"] for s in servicios) + sum(r["importe"] for r in refacciones if r["estatus"] == "surtida")
    return cab, servicios, refacciones, total


def servicios_catalogo(cur):
    cur.execute("SELECT id_servicio, nombre, precio_base FROM servicio ORDER BY nombre")
    return cur.fetchall()


def productos_catalogo(cur):
    cur.execute("SELECT id_producto, codigo, nombre, stock_actual FROM producto ORDER BY nombre")
    return cur.fetchall()


def _orden_editable(cur, id_orden):
    cur.execute("SELECT estatus FROM orden_trabajo WHERE id_orden = %s FOR UPDATE", (id_orden,))
    fila = cur.fetchone()
    if fila is None:
        raise TallerError("La orden no existe.")
    if fila["estatus"] not in EDITABLES:
        raise TallerError("La orden está %s y ya no admite cambios." % ETIQUETA_ESTATUS[fila["estatus"]].lower())
    return fila["estatus"]


def agregar_servicio(conn, id_orden, id_servicio):
    """Agrega un servicio a la orden con el precio base vigente (no se repite el mismo servicio)."""
    id_servicio = _entero(id_servicio, "El servicio", 1)
    cur = conn.cursor()
    try:
        _orden_editable(cur, id_orden)
        cur.execute("SELECT precio_base FROM servicio WHERE id_servicio = %s", (id_servicio,))
        s = cur.fetchone()
        if s is None:
            raise TallerError("El servicio seleccionado no existe.")
        cur.execute("SELECT 1 FROM detalle_orden_servicio WHERE id_orden = %s AND id_servicio = %s", (id_orden, id_servicio))
        if cur.fetchone():
            raise TallerError("Ese servicio ya está en la orden.")
        cur.execute("INSERT INTO detalle_orden_servicio (id_orden, id_servicio, precio_aplicado) VALUES (%s,%s,%s)",
                    (id_orden, id_servicio, s["precio_base"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def solicitar_refaccion(conn, id_usuario, id_orden, id_producto, cantidad):
    """Solicita una refacción para la orden. Si hay existencia se surte y descuenta el stock; si no, queda
    registrada como «sin existencia». Devuelve el estatus de la solicitud ('surtida' o 'sin_existencia')."""
    id_producto = _entero(id_producto, "La refacción", 1)
    cantidad = _entero(cantidad, "La cantidad", 1, 999)
    cur = conn.cursor()
    try:
        _orden_editable(cur, id_orden)
        cur.execute("SELECT stock_actual FROM producto WHERE id_producto = %s FOR UPDATE", (id_producto,))
        p = cur.fetchone()
        if p is None:
            raise TallerError("La refacción seleccionada no existe.")
        if p["stock_actual"] >= cantidad:
            estatus = "surtida"
            cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, referencia)
                           VALUES (%s,%s,'salida',%s,%s)""", (id_producto, id_usuario, cantidad, "ORDEN-%d" % id_orden))
        else:
            estatus = "sin_existencia"
        cur.execute("INSERT INTO solicitud_refaccion (id_orden, id_producto, cantidad, estatus) VALUES (%s,%s,%s,%s)",
                    (id_orden, id_producto, cantidad, estatus))
        conn.commit()
        return estatus
    except Exception:
        conn.rollback()
        raise


def cambiar_estatus(conn, id_usuario, id_orden, nuevo):
    """Avanza la orden de estatus. Al entregar se registra la fecha y se actualiza el kilometraje del vehículo;
    al cancelar se devuelven al inventario las refacciones ya surtidas."""
    if nuevo not in ESTATUS_ORDEN:
        raise TallerError("Estatus no válido.")
    cur = conn.cursor()
    try:
        cur.execute("SELECT estatus, id_vehiculo, kilometraje_ingreso FROM orden_trabajo WHERE id_orden = %s FOR UPDATE", (id_orden,))
        o = cur.fetchone()
        if o is None:
            raise TallerError("La orden no existe.")
        if nuevo not in TRANSICIONES[o["estatus"]]:
            raise TallerError("No se puede pasar una orden %s a %s." % (ETIQUETA_ESTATUS[o["estatus"]].lower(), ETIQUETA_ESTATUS[nuevo].lower()))
        if nuevo == "entregada":
            cur.execute("UPDATE orden_trabajo SET estatus = 'entregada', fecha_entrega = now() WHERE id_orden = %s", (id_orden,))
            cur.execute("UPDATE vehiculo SET kilometraje_actual = GREATEST(kilometraje_actual, %s) WHERE id_vehiculo = %s",
                        (o["kilometraje_ingreso"], o["id_vehiculo"]))
        else:
            cur.execute("UPDATE orden_trabajo SET estatus = %s WHERE id_orden = %s", (nuevo, id_orden))
        if nuevo == "cancelada":
            cur.execute("SELECT id_solicitud, id_producto, cantidad FROM solicitud_refaccion WHERE id_orden = %s AND estatus = 'surtida'", (id_orden,))
            for s in cur.fetchall():
                cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, referencia)
                               VALUES (%s,%s,'entrada',%s,%s)""", (s["id_producto"], id_usuario, s["cantidad"], "CANCELA-ORDEN-%d" % id_orden))
            cur.execute("UPDATE solicitud_refaccion SET estatus = 'cancelada' WHERE id_orden = %s AND estatus IN ('surtida','pendiente')", (id_orden,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
