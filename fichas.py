"""Genera fichas DEMO (marca, características, compatibilidad y ubicación) para refacciones de ejemplo.
Los datos son orientativos y sirven solo para probar el sistema; el taller los reemplazará con los reales."""
import re
import zlib

MARCAS = {"Frenos": ["Fritec", "Brembo", "Bendix"], "Lubricantes": ["Mobil", "Castrol", "Valvoline"], "Encendido": ["NGK", "Bosch", "Denso"],
          "Suspensión": ["Monroe", "KYB", "Moog"], "Llantas": ["Michelin", "Bridgestone", "Goodyear"], "Bandas y mangueras": ["Gates", "Dayco", "Goodyear"],
          "Filtros": ["Fram", "Gonher", "Bosch"], "Eléctrico": ["LTH", "Bosch", "Philips"], "Dirección": ["Moog", "TRW", "Delphi"],
          "Refrigeración": ["Gonher", "Gates", "Prestone"], "Transmisión": ["LuK", "SKF", "Valeo"], "Accesorios": ["Bosch", "Trico", "Universal"]}
DESC = {"Frenos": "Material de fricción de baja emisión de polvo; incluye herrajes. Se recomienda cambiar por eje.",
        "Lubricantes": "Protección contra desgaste y depósitos. Cumple especificaciones API vigentes.",
        "Encendido": "Electrodo de larga duración; mejora el arranque y el consumo de combustible.",
        "Suspensión": "Pieza nueva con garantía contra defectos de fábrica; se recomienda cambiar en pares.",
        "Llantas": "Banda de rodamiento para uso mixto ciudad-carretera; incluye índice de carga y velocidad en el costado.",
        "Bandas y mangueras": "Compuesto resistente a calor y aceite; verificar medida contra la pieza original.",
        "Filtros": "Elemento filtrante de alta eficiencia; reemplazo directo de equipo original.",
        "Eléctrico": "12 V. Probado antes de su venta; garantía de 6 a 12 meses según la pieza.",
        "Dirección": "Pieza de reemplazo con sello de protección; requiere alineación después de instalarse.",
        "Refrigeración": "Resistente a presión y temperatura del sistema; usar con anticongelante 50/50.",
        "Transmisión": "Pieza nueva o reconstruida de calidad equivalente al equipo original.",
        "Accesorios": "Accesorio de uso general, de instalación sencilla."}
ESTANTE = {"Frenos": "A", "Lubricantes": "B", "Encendido": "C", "Suspensión": "D", "Llantas": "E", "Bandas y mangueras": "F",
           "Filtros": "G", "Eléctrico": "H", "Dirección": "I", "Refrigeración": "J", "Transmisión": "K", "Accesorios": "L"}
AUTOS = r"(Nissan|Chevrolet|Volkswagen|Toyota|Honda|Ford|Kia|Hyundai|Mazda|Suzuki)\s+([A-Za-z0-9\-]+(?:/[A-Za-z0-9\-]+)*)"


def ficha(categoria, nombre, codigo):
    """Devuelve (marca, descripcion, compatibilidad, ubicacion) determinista para un producto."""
    h = zlib.crc32(codigo.encode())
    marca = MARCAS.get(categoria, ["Genérica"])[h % len(MARCAS.get(categoria, ["Genérica"]))]
    m = re.search(AUTOS, nombre)
    compat = "%s %s" % (m.group(1), m.group(2).replace("/", " / ")) if m else "Universal / consultar compatibilidad"
    ubic = "Estante %s-%d" % (ESTANTE.get(categoria, "Z"), 1 + h % 6)
    return marca, DESC.get(categoria, "Refacción de uso general."), compat, ubic


def completar(conn, confirmar=True):
    """Llena la ficha de las refacciones que aún no la tienen (para bases creadas antes de esta versión)."""
    cur = conn.cursor()
    cur.execute("""SELECT p.id_producto, p.codigo, p.nombre, c.nombre AS categoria FROM producto p
                     JOIN categoria c ON c.id_categoria = p.id_categoria
                    WHERE p.marca IS NULL AND p.descripcion IS NULL AND p.compatibilidad IS NULL AND p.ubicacion IS NULL""")
    for r in cur.fetchall():
        cur2 = conn.cursor()
        cur2.execute("UPDATE producto SET marca=%s, descripcion=%s, compatibilidad=%s, ubicacion=%s WHERE id_producto=%s",
                     ficha(r["categoria"], r["nombre"], r["codigo"]) + (r["id_producto"],))
    if confirmar:
        conn.commit()
