"""Catálogo de refacciones: alta, consulta, edición y entradas de mercancía.

Cada refacción tiene una ficha con identificador, código, nombre, marca, características,
compatibilidad, ubicación en la refaccionaria, proveedor, precios y existencias.
Las existencias solo cambian mediante movimientos de inventario (entrada, salida o ajuste),
de modo que la bitácora siempre explica el stock actual.
"""
from decimal import Decimal, InvalidOperation


class CatalogoError(Exception):
    """Error de validación con mensaje para el usuario."""


def _texto(v, nombre, maximo, obligatorio=False):
    v = (v or "").strip()
    if obligatorio and not v:
        raise CatalogoError("%s es obligatorio." % nombre)
    if len(v) > maximo:
        raise CatalogoError("%s no puede tener más de %d caracteres." % (nombre, maximo))
    return v or None


def _precio(v, nombre, obligatorio=True):
    v = str(v if v is not None else "").replace("$", "").replace(",", "").strip()
    if not v:
        if obligatorio:
            raise CatalogoError("%s es obligatorio." % nombre)
        return Decimal("0.00")
    try:
        d = Decimal(v)
    except InvalidOperation:
        raise CatalogoError("%s debe ser un número." % nombre)
    if d < 0 or d > Decimal("99999999.99"):
        raise CatalogoError("%s debe estar entre 0 y 99,999,999.99." % nombre)
    return d.quantize(Decimal("0.01"))


def _entero(v, nombre, minimo=0, maximo=1000000, obligatorio=True):
    if v in (None, ""):
        if obligatorio:
            raise CatalogoError("%s es obligatorio." % nombre)
        return 0
    try:
        n = int(str(v).strip())
    except ValueError:
        raise CatalogoError("%s debe ser un número entero." % nombre)
    if n < minimo or n > maximo:
        raise CatalogoError("%s debe estar entre %d y %d." % (nombre, minimo, maximo))
    return n


def categorias(cur):
    cur.execute("SELECT id_categoria, nombre FROM categoria ORDER BY nombre")
    return cur.fetchall()


def proveedores(cur):
    cur.execute("SELECT id_proveedor, nombre FROM proveedor ORDER BY nombre")
    return cur.fetchall()


def listar(cur, texto="", id_categoria=None):
    """Refacciones con categoría, precio y estatus de existencia, filtradas por texto y categoría."""
    patron = "%" + texto.strip() + "%"
    cur.execute("""SELECT p.id_producto, p.codigo, p.nombre, p.marca, p.ubicacion, p.precio_venta, p.stock_actual, p.stock_minimo,
                          c.nombre AS categoria,
                          CASE WHEN p.stock_actual = 0 THEN 'sin existencia'
                               WHEN p.stock_actual <= p.stock_minimo THEN 'reabastecer'
                               WHEN p.stock_actual <= p.stock_minimo * 1.5 THEN 'próximo al mínimo'
                               ELSE 'suficiente' END AS estatus
                     FROM producto p JOIN categoria c ON c.id_categoria = p.id_categoria
                    WHERE (p.nombre ILIKE %s OR p.codigo ILIKE %s OR COALESCE(p.marca,'') ILIKE %s OR COALESCE(p.compatibilidad,'') ILIKE %s)
                      AND (%s::int IS NULL OR p.id_categoria = %s::int)
                    ORDER BY p.nombre""", (patron, patron, patron, patron, id_categoria, id_categoria))
    return cur.fetchall()


def obtener(cur, id_producto):
    """Ficha completa de una refacción con margen de utilidad, o None si no existe."""
    cur.execute("""SELECT p.*, c.nombre AS categoria, pr.nombre AS proveedor,
                          p.precio_venta - p.precio_compra AS utilidad,
                          CASE WHEN p.precio_compra > 0 THEN round((p.precio_venta - p.precio_compra) / p.precio_compra * 100, 1) END AS margen_pct,
                          CASE WHEN p.stock_actual = 0 THEN 'sin existencia'
                               WHEN p.stock_actual <= p.stock_minimo THEN 'reabastecer'
                               WHEN p.stock_actual <= p.stock_minimo * 1.5 THEN 'próximo al mínimo'
                               ELSE 'suficiente' END AS estatus
                     FROM producto p JOIN categoria c ON c.id_categoria = p.id_categoria
                     LEFT JOIN proveedor pr ON pr.id_proveedor = p.id_proveedor
                    WHERE p.id_producto = %s""", (id_producto,))
    return cur.fetchone()


def movimientos(cur, id_producto, limite=15):
    """Últimos movimientos de inventario de la refacción (bitácora)."""
    cur.execute("""SELECT m.fecha, m.tipo, m.cantidad, m.referencia, u.nombre_completo AS usuario
                     FROM movimiento_inventario m JOIN usuario u ON u.id_usuario = m.id_usuario
                    WHERE m.id_producto = %s ORDER BY m.id_movimiento DESC LIMIT %s""", (id_producto, limite))
    return cur.fetchall()


def guardar(conn, id_usuario, datos, id_producto=None):
    """Crea o actualiza una refacción y devuelve su id.

    Al crear, la existencia inicial entra como movimiento de «entrada» (referencia ALTA-INICIAL).
    Al editar no se modifica la existencia: para eso se usa registrar_entrada o un ajuste.
    """
    codigo = _texto(datos.get("codigo"), "El código", 20, True).upper().replace(" ", "")
    nombre = _texto(datos.get("nombre"), "El nombre", 100, True)
    marca = _texto(datos.get("marca"), "La marca", 50)
    descripcion = _texto(datos.get("descripcion"), "Las características", 300)
    compat = _texto(datos.get("compatibilidad"), "La compatibilidad", 200)
    ubic = _texto(datos.get("ubicacion"), "La ubicación", 30)
    compra = _precio(datos.get("precio_compra"), "El precio de compra", obligatorio=False)
    venta = _precio(datos.get("precio_venta"), "El precio de venta")
    minimo = _entero(datos.get("stock_minimo"), "El stock mínimo", obligatorio=False)
    id_cat = _entero(datos.get("id_categoria"), "La categoría", 1)
    id_prov = _entero(datos.get("id_proveedor"), "El proveedor", 1, obligatorio=False) or None
    inicial = _entero(datos.get("stock_inicial"), "La existencia inicial", 0, obligatorio=False) if id_producto is None else 0
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM categoria WHERE id_categoria = %s", (id_cat,))
        if cur.fetchone() is None:
            raise CatalogoError("La categoría seleccionada no existe.")
        if id_prov:
            cur.execute("SELECT 1 FROM proveedor WHERE id_proveedor = %s", (id_prov,))
            if cur.fetchone() is None:
                raise CatalogoError("El proveedor seleccionado no existe.")
        cur.execute("SELECT id_producto FROM producto WHERE codigo = %s", (codigo,))
        otro = cur.fetchone()
        if otro and otro["id_producto"] != id_producto:
            raise CatalogoError("Ya existe una refacción con el código %s." % codigo)
        if id_producto is None:
            cur.execute("""INSERT INTO producto (id_categoria, id_proveedor, codigo, nombre, marca, descripcion, compatibilidad, ubicacion,
                                                 precio_compra, precio_venta, stock_actual, stock_minimo)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s) RETURNING id_producto""",
                        (id_cat, id_prov, codigo, nombre, marca, descripcion, compat, ubic, compra, venta, minimo))
            id_producto = cur.fetchone()["id_producto"]
            if inicial:
                cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, referencia)
                               VALUES (%s,%s,'entrada',%s,'ALTA-INICIAL')""", (id_producto, id_usuario, inicial))
        else:
            cur.execute("""UPDATE producto SET id_categoria=%s, id_proveedor=%s, codigo=%s, nombre=%s, marca=%s, descripcion=%s,
                                  compatibilidad=%s, ubicacion=%s, precio_compra=%s, precio_venta=%s, stock_minimo=%s
                            WHERE id_producto=%s""",
                        (id_cat, id_prov, codigo, nombre, marca, descripcion, compat, ubic, compra, venta, minimo, id_producto))
            if cur.rowcount == 0:
                raise CatalogoError("La refacción no existe.")
        conn.commit()
        return id_producto
    except Exception:
        conn.rollback()
        raise


def registrar_entrada(conn, id_usuario, id_producto, cantidad, motivo=""):
    """Suma piezas a la existencia (compra o devolución) dejando constancia en la bitácora."""
    cantidad = _entero(cantidad, "La cantidad", 1, 100000)
    motivo = _texto(motivo, "El motivo", 38) or "compra"
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM producto WHERE id_producto = %s FOR UPDATE", (id_producto,))
        if cur.fetchone() is None:
            raise CatalogoError("La refacción no existe.")
        cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, referencia)
                       VALUES (%s,%s,'entrada',%s,%s)""", (id_producto, id_usuario, cantidad, "ENTRADA: " + motivo))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
