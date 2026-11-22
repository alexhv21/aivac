"""Importa el catálogo real del taller desde un archivo CSV (o Excel .xlsx) a la base de datos.

Uso:
    python import_catalogo.py catalogo.csv                 # refacciones
    python import_catalogo.py servicios.csv --servicios    # servicios
    python import_catalogo.py catalogo.csv --simular       # solo valida; no guarda nada

Columnas de refacciones (la primera fila son los encabezados; el orden no importa):
    codigo, nombre, categoria, proveedor, precio_compra, precio_venta, stock, stock_minimo
Columnas de servicios:
    nombre, precio_base

Reglas:
  * Si el código ya existe se actualizan nombre, categoría, proveedor, precios y mínimo; si el stock del
    archivo es distinto al del sistema se registra un movimiento de «ajuste» con la diferencia.
  * Si el código no existe se crea la refacción y su existencia inicial entra como movimiento de «entrada».
  * Las categorías y proveedores que no existan se crean.
  * Si alguna fila tiene errores NO se guarda nada y se muestran todos los errores con su número de fila.
"""
import argparse
import csv
import io
import re
import sys
from decimal import Decimal, InvalidOperation

import db

ENCABEZADOS_PRODUCTO = ("codigo", "nombre", "categoria", "proveedor", "precio_compra", "precio_venta", "stock", "stock_minimo")
OBLIGATORIAS = ("codigo", "nombre", "categoria", "precio_venta", "stock")


def _norm(t):
    t = (t or "").strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(a, b)
    return re.sub(r"[\s\-]+", "_", t)


def leer_filas(ruta):
    """Devuelve una lista de diccionarios con encabezados normalizados, desde CSV o XLSX."""
    if ruta.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError:
            sys.exit("Para leer Excel instale openpyxl (pip install openpyxl) o guarde el archivo como CSV.")
        hoja = openpyxl.load_workbook(ruta, read_only=True, data_only=True).active
        filas = list(hoja.iter_rows(values_only=True))
        enc = [_norm(str(c)) if c is not None else "" for c in filas[0]]
        return [dict(zip(enc, ["" if c is None else str(c) for c in f])) for f in filas[1:] if any(c is not None for c in f)]
    with open(ruta, "rb") as f:
        crudo = f.read()
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = crudo.decode("cp1252")
    muestra = texto[:2000]
    delim = ";" if muestra.count(";") > muestra.count(",") else ","
    lector = csv.reader(io.StringIO(texto), delimiter=delim)
    filas = [f for f in lector if any(c.strip() for c in f)]
    enc = [_norm(c) for c in filas[0]]
    return [dict(zip(enc, f)) for f in filas[1:]]


def _dinero(valor, nombre, errores, fila, minimo=0, obligatorio=True):
    v = (valor or "").strip().replace("$", "").replace(",", "")
    if not v:
        if obligatorio:
            errores.append("Fila %d: falta %s." % (fila, nombre))
        return Decimal(0)
    try:
        d = Decimal(v)
    except InvalidOperation:
        errores.append("Fila %d: %s «%s» no es un número." % (fila, nombre, valor))
        return Decimal(0)
    if d < minimo:
        errores.append("Fila %d: %s no puede ser negativo." % (fila, nombre))
    return d


def importar_productos(conn, filas, id_usuario, simular=False):
    """Importa refacciones. Devuelve (creadas, actualizadas, errores)."""
    errores, preparadas, vistos = [], [], set()
    for i, f in enumerate(filas, start=2):
        for col in OBLIGATORIAS:
            if not (f.get(col) or "").strip():
                errores.append("Fila %d: falta la columna «%s»." % (i, col))
        codigo = (f.get("codigo") or "").strip().upper()
        if codigo in vistos:
            errores.append("Fila %d: el código %s está repetido en el archivo." % (i, codigo))
        vistos.add(codigo)
        if len(codigo) > 20:
            errores.append("Fila %d: el código %s excede 20 caracteres." % (i, codigo))
        compra = _dinero(f.get("precio_compra"), "precio_compra", errores, i, obligatorio=False)
        venta = _dinero(f.get("precio_venta"), "precio_venta", errores, i)
        stock = _dinero(f.get("stock"), "stock", errores, i)
        minimo = _dinero(f.get("stock_minimo"), "stock_minimo", errores, i, obligatorio=False)
        if stock != stock.to_integral_value() or minimo != minimo.to_integral_value():
            errores.append("Fila %d: stock y stock_minimo deben ser enteros." % i)
        preparadas.append((codigo, (f.get("nombre") or "").strip()[:100], (f.get("categoria") or "").strip()[:50],
                           (f.get("proveedor") or "").strip()[:100], compra, venta, int(stock), int(minimo)))
    if errores:
        return 0, 0, errores
    cur = conn.cursor()
    creadas = actualizadas = 0
    try:
        for codigo, nombre, cat, prov, compra, venta, stock, minimo in preparadas:
            cur.execute("SELECT id_categoria FROM categoria WHERE lower(nombre) = lower(%s)", (cat,))
            r = cur.fetchone()
            if r is None:
                cur.execute("INSERT INTO categoria (nombre) VALUES (%s) RETURNING id_categoria", (cat,))
                r = cur.fetchone()
            id_cat = r["id_categoria"]
            id_prov = None
            if prov:
                cur.execute("SELECT id_proveedor FROM proveedor WHERE lower(nombre) = lower(%s)", (prov,))
                r = cur.fetchone()
                if r is None:
                    cur.execute("INSERT INTO proveedor (nombre) VALUES (%s) RETURNING id_proveedor", (prov,))
                    r = cur.fetchone()
                id_prov = r["id_proveedor"]
            cur.execute("SELECT id_producto, stock_actual FROM producto WHERE codigo = %s FOR UPDATE", (codigo,))
            p = cur.fetchone()
            if p is None:
                cur.execute("""INSERT INTO producto (id_categoria, id_proveedor, codigo, nombre, precio_compra, precio_venta, stock_actual, stock_minimo)
                               VALUES (%s,%s,%s,%s,%s,%s,0,%s) RETURNING id_producto""", (id_cat, id_prov, codigo, nombre, compra, venta, minimo))
                idp = cur.fetchone()["id_producto"]
                if stock:
                    cur.execute("INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, referencia) VALUES (%s,%s,'entrada',%s,'IMPORTACION')",
                                (idp, id_usuario, stock))
                creadas += 1
            else:
                cur.execute("""UPDATE producto SET id_categoria=%s, id_proveedor=%s, nombre=%s, precio_compra=%s, precio_venta=%s, stock_minimo=%s
                                WHERE id_producto=%s""", (id_cat, id_prov, nombre, compra, venta, minimo, p["id_producto"]))
                if stock != p["stock_actual"]:
                    cur.execute("INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, referencia) VALUES (%s,%s,'ajuste',%s,'IMPORTACION')",
                                (p["id_producto"], id_usuario, stock - p["stock_actual"]))
                actualizadas += 1
        if simular:
            conn.rollback()
        else:
            conn.commit()
        return creadas, actualizadas, []
    except Exception:
        conn.rollback()
        raise


def importar_servicios(conn, filas, simular=False):
    errores, preparadas = [], []
    for i, f in enumerate(filas, start=2):
        nombre = (f.get("nombre") or "").strip()
        if not nombre:
            errores.append("Fila %d: falta el nombre." % i)
        precio = _dinero(f.get("precio_base"), "precio_base", errores, i)
        preparadas.append((nombre[:80], precio))
    if errores:
        return 0, 0, errores
    cur = conn.cursor()
    creadas = actualizadas = 0
    try:
        for nombre, precio in preparadas:
            cur.execute("SELECT id_servicio FROM servicio WHERE lower(nombre) = lower(%s)", (nombre,))
            r = cur.fetchone()
            if r is None:
                cur.execute("INSERT INTO servicio (nombre, precio_base) VALUES (%s,%s)", (nombre, precio)); creadas += 1
            else:
                cur.execute("UPDATE servicio SET precio_base = %s WHERE id_servicio = %s", (precio, r["id_servicio"])); actualizadas += 1
        conn.rollback() if simular else conn.commit()
        return creadas, actualizadas, []
    except Exception:
        conn.rollback()
        raise


def main():
    ap = argparse.ArgumentParser(description="Importa el catálogo del taller desde CSV o Excel.")
    ap.add_argument("archivo")
    ap.add_argument("--servicios", action="store_true", help="el archivo contiene servicios (nombre, precio_base)")
    ap.add_argument("--simular", action="store_true", help="solo validar, sin guardar")
    ap.add_argument("--usuario", default="refacciones", help="usuario al que se atribuyen los movimientos de inventario")
    a = ap.parse_args()
    conn = db.conectar()
    cur = conn.cursor()
    cur.execute("SELECT id_usuario FROM usuario WHERE nombre_usuario = %s", (a.usuario,))
    u = cur.fetchone()
    if u is None and not a.servicios:
        sys.exit("No existe el usuario «%s». Indique uno válido con --usuario." % a.usuario)
    filas = leer_filas(a.archivo)
    if a.servicios:
        c, m, err = importar_servicios(conn, filas, a.simular)
    else:
        c, m, err = importar_productos(conn, filas, u["id_usuario"], a.simular)
    conn.close()
    if err:
        print("NO SE IMPORTÓ NADA. Corrija estos errores y vuelva a intentarlo:")
        for e in err[:50]:
            print("  -", e)
        sys.exit(1)
    print(("SIMULACIÓN (no se guardó nada): " if a.simular else "Importación terminada: ") + "%d nuevos y %d actualizados." % (c, m))


if __name__ == "__main__":
    main()
