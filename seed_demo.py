"""Carga datos DEMO ficticios para probar el sistema (usuarios, clientes, vehículos, catálogo,
ventas y órdenes de trabajo históricas, y seguimiento de componentes).

Solo para desarrollo y pruebas: todos los nombres, teléfonos, placas y precios son inventados.
Uso:  AIVAC_DSN="dbname=aivac ..." python seed_demo.py
Si la base ya tiene usuarios no hace nada (para no duplicar). Es determinista: siempre carga lo mismo.
Las existencias finales de cada refacción son las definidas en el catálogo; el sistema registra una
«compra inicial» y las salidas por ventas y órdenes para que la bitácora cuadre con el stock.
"""
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

import db
import fichas

CONTRASENA_DEMO = "Demo2026!"
AHORA = datetime(2026, 11, 9, 18, 0)  # fecha de referencia fija de los datos históricos

USUARIOS = [("Gerente Principal", "Gerente Principal (demo)", "gerente.principal"),
            ("Gerente Administrativa", "Gerente Administrativa (demo)", "gerente.admin"),
            ("Jefe de Refaccionaria", "Jefe de Refaccionaria (demo)", "refacciones"),
            ("Mecánico", "Mecánico 1 (demo)", "mecanico1"),
            ("Repartidor", "Repartidor (demo)", "repartidor"),
            ("Mecánico", "Mecánico 2 (demo)", "mecanico2"),
            ("Mecánico", "Mecánico 3 (demo)", "mecanico3")]

CLIENTES = [  # (nombre, tipo, teléfono, correo)
    ("Juan Pérez Demo", "particular", "9511000001", None), ("Transportes Ejemplo S.A.", "flotilla", "9511000002", "contacto@transportes-ejemplo.mx"),
    ("María López Demo", "particular", "9511000003", None), ("Taller Hermano Demo", "taller", "9511000004", None),
    ("Carlos Mendoza Ruiz", "particular", "9512204411", "cmendoza@correo.mx"), ("Ana Sofía Hernández", "particular", "9512208032", None),
    ("Roberto Santiago Cruz", "particular", "9511187723", None), ("Lucía Martínez Vásquez", "particular", "9513305590", "lucia.mv@correo.mx"),
    ("Miguel Ángel Ortiz", "particular", "9512761045", None), ("Fernanda Aguilar Ramos", "particular", "9511432288", None),
    ("Distribuidora Oaxaca Norte", "flotilla", "9515501200", "compras@dist-oaxnorte.mx"), ("Abarrotes La Esperanza", "flotilla", "9515502301", None),
    ("Paquetería Rápida del Valle", "flotilla", "9515503402", "flota@pqvalle.mx"), ("Refrigerados Monte Albán", "flotilla", "9515504503", None),
    ("Taller Mecánico El Chino", "taller", "9516601144", None), ("Autoservicio Gómez", "taller", "9516602255", None),
    ("Jorge Luis Díaz", "particular", "9511903371", None), ("Patricia Flores Gómez", "particular", "9512914480", "paty.flores@correo.mx"),
    ("Héctor Ramírez Torres", "particular", "9513925592", None), ("Gabriela Jiménez León", "particular", "9514936603", None),
    ("Eduardo Castillo Pérez", "particular", "9511947714", None), ("Sandra Morales Cruz", "particular", "9512958825", None),
    ("Víctor Manuel Reyes", "particular", "9513969936", None), ("Daniela Vargas Ruiz", "particular", "9514970047", "dvargas@correo.mx"),
    ("Mudanzas y Fletes Istmo", "flotilla", "9515505604", None)]

VEHICULOS = [  # (índice de cliente 1-based, placas, marca, modelo, año, uso, km)
    (1, "OAX-123", "Nissan", "Versa", 2018, "particular", 48000), (2, "OAX-908", "Ford", "Transit", 2020, "reparto", 92000),
    (3, "OAX-555", "Chevrolet", "Aveo", 2016, "particular", 120000), (5, "TJK-41-22", "Volkswagen", "Jetta", 2017, "particular", 83500),
    (6, "TJK-52-31", "Nissan", "March", 2019, "particular", 41200), (7, "TJL-10-09", "Toyota", "Corolla", 2015, "particular", 134800),
    (8, "TJL-27-45", "Honda", "CR-V", 2018, "particular", 77600), (9, "TJM-33-18", "Chevrolet", "Spark", 2017, "particular", 66400),
    (10, "TJM-48-60", "Kia", "Rio", 2020, "particular", 38900), (11, "OAX-3101", "Nissan", "NP300", 2019, "reparto", 112400),
    (11, "OAX-3102", "Nissan", "NP300", 2021, "reparto", 74200), (12, "OAX-3203", "Ford", "Ranger", 2018, "reparto", 129800),
    (13, "OAX-3304", "Ford", "Transit", 2022, "reparto", 58100), (13, "OAX-3305", "Nissan", "Urvan", 2020, "reparto", 97300),
    (14, "OAX-3406", "Hyundai", "H100", 2019, "reparto", 143700), (15, "TJN-15-77", "Chevrolet", "Silverado", 2014, "particular", 188000),
    (16, "TJN-26-88", "Nissan", "Tsuru", 2012, "particular", 214500), (17, "TJP-37-99", "Mazda", "Mazda 3", 2016, "particular", 98700),
    (18, "TJP-48-10", "Volkswagen", "Vento", 2019, "particular", 52300), (19, "TJQ-59-21", "Toyota", "Hilux", 2017, "particular", 121000),
    (20, "TJQ-60-32", "Suzuki", "Swift", 2018, "particular", 59800), (21, "TJR-71-43", "Ford", "Fiesta", 2015, "particular", 109400),
    (22, "TJR-82-54", "Chevrolet", "Onix", 2021, "particular", 31500), (23, "TJS-93-65", "Nissan", "Sentra", 2017, "particular", 91200),
    (24, "TJS-04-76", "Honda", "Civic", 2016, "particular", 115600), (25, "OAX-3507", "Isuzu", "NHR", 2018, "reparto", 156900),
    (25, "OAX-3508", "Hino", "300", 2020, "reparto", 101800), (4, "TJT-15-87", "Nissan", "Frontier", 2013, "particular", 176300),
    (10, "TJT-26-98", "Kia", "Sportage", 2022, "particular", 24800), (6, "TJU-37-09", "Renault", "Duster", 2019, "particular", 62700)]

PROVEEDORES = [("Distribuidora del Valle (demo)", "9511000101"), ("Refacciones del Sur (demo)", "9511000102"),
               ("Lubricantes y Filtros del Istmo (demo)", "9511000103"), ("Autopartes Eléctricas Oaxaca (demo)", "9511000104"),
               ("Llantas y Rines Monte Albán (demo)", "9511000105"), ("Suspensión y Dirección MX (demo)", "9511000106")]

CATEGORIAS_EXTRA = ["Filtros", "Eléctrico", "Dirección", "Refrigeración", "Transmisión", "Accesorios"]

SERVICIOS_EXTRA = [("Cambio de amortiguadores (por eje)", 600), ("Cambio de bujías", 280), ("Cambio de banda de accesorios", 350),
                   ("Cambio de filtro de aire", 120), ("Cambio de llantas (4 piezas)", 400), ("Rotación de llantas", 180),
                   ("Diagnóstico por computadora", 450), ("Cambio de batería", 150), ("Servicio de frenos completo", 900),
                   ("Cambio de anticongelante", 380), ("Cambio de discos de freno", 550), ("Revisión general 20 puntos", 250)]

# (categoría, proveedor 1-based, código, nombre, compra, venta, stock final, mínimo)
PRODUCTOS = [
    ("Frenos", 1, "BAL-001", "Balatas delanteras Nissan Versa", 380, 520, 12, 4), ("Frenos", 1, "BAL-002", "Balatas traseras Nissan Versa", 300, 450, 8, 4),
    ("Lubricantes", 2, "ACE-5W30", "Aceite sintético 5W-30 (litro)", 110, 165, 40, 12), ("Lubricantes", 2, "FIL-ACE1", "Filtro de aceite universal", 60, 95, 25, 8),
    ("Encendido", 1, "BUJ-NGK4", "Juego de bujías NGK (4 piezas)", 240, 360, 3, 5), ("Suspensión", 2, "AMO-DEL1", "Amortiguador delantero", 650, 890, 2, 2),
    ("Suspensión", 2, "AMO-TRA1", "Amortiguador trasero", 520, 740, 0, 2), ("Llantas", 1, "LLA-185", "Llanta 185/65 R15", 1100, 1450, 10, 4),
    ("Bandas y mangueras", 2, "BAN-SER1", "Banda de accesorios", 150, 230, 9, 3), ("Frenos", 1, "DIS-DEL1", "Disco de freno delantero", 480, 690, 6, 2),
    ("Frenos", 1, "BAL-003", "Balatas delanteras Chevrolet Aveo", 360, 495, 7, 4), ("Frenos", 1, "BAL-004", "Balatas delanteras Volkswagen Jetta", 420, 580, 6, 4),
    ("Frenos", 1, "BAL-005", "Balatas delanteras Toyota Corolla", 450, 620, 5, 3), ("Frenos", 1, "BAL-006", "Balatas traseras Chevrolet Aveo", 290, 430, 6, 3),
    ("Frenos", 1, "DIS-TRA1", "Disco de freno trasero", 430, 610, 4, 2), ("Frenos", 1, "LIQ-FRE1", "Líquido de frenos DOT 4 (500 ml)", 70, 115, 22, 8),
    ("Frenos", 1, "BAL-007", "Balatas delanteras Ford Ranger", 520, 710, 3, 3), ("Frenos", 1, "BAL-008", "Balatas delanteras Nissan NP300", 500, 690, 4, 3),
    ("Lubricantes", 3, "ACE-10W40", "Aceite semisintético 10W-40 (litro)", 85, 130, 48, 14), ("Lubricantes", 3, "ACE-15W40D", "Aceite diésel 15W-40 (litro)", 95, 145, 30, 10),
    ("Lubricantes", 3, "ACE-ATF1", "Aceite para transmisión ATF (litro)", 120, 175, 18, 6), ("Lubricantes", 3, "GRA-MP1", "Grasa multiusos (400 g)", 55, 90, 14, 4),
    ("Lubricantes", 3, "ANT-50-1", "Anticongelante 50/50 (galón)", 140, 215, 16, 6), ("Filtros", 3, "FIL-AIR1", "Filtro de aire Nissan Versa/March", 90, 145, 15, 5),
    ("Filtros", 3, "FIL-AIR2", "Filtro de aire Chevrolet Aveo/Spark", 85, 140, 10, 5), ("Filtros", 3, "FIL-AIR3", "Filtro de aire Volkswagen Jetta/Vento", 110, 170, 8, 4),
    ("Filtros", 3, "FIL-COM1", "Filtro de combustible universal", 75, 125, 20, 6), ("Filtros", 3, "FIL-ACE2", "Filtro de aceite Toyota/Honda", 70, 110, 18, 6),
    ("Filtros", 3, "FIL-CAB1", "Filtro de cabina (aire acondicionado)", 100, 160, 9, 4), ("Filtros", 3, "FIL-DIE1", "Filtro de diésel NP300/Ranger", 130, 195, 7, 3),
    ("Encendido", 4, "BUJ-NGK6", "Juego de bujías NGK (6 piezas)", 360, 520, 4, 3), ("Encendido", 4, "BUJ-BOS4", "Juego de bujías Bosch (4 piezas)", 260, 385, 6, 4),
    ("Encendido", 4, "CAB-BUJ1", "Juego de cables de bujía", 280, 420, 5, 3), ("Encendido", 4, "BOB-ENC1", "Bobina de encendido", 380, 590, 4, 2),
    ("Eléctrico", 4, "BAT-35", "Batería 35 placas (12 V)", 1250, 1690, 6, 3), ("Eléctrico", 4, "BAT-42", "Batería 42 placas (12 V)", 1480, 1980, 4, 3),
    ("Eléctrico", 4, "ALT-001", "Alternador reconstruido universal", 1900, 2650, 2, 1), ("Eléctrico", 4, "MAR-001", "Marcha reconstruida universal", 1700, 2380, 2, 1),
    ("Eléctrico", 4, "FOC-H4", "Foco halógeno H4 (par)", 95, 160, 18, 6), ("Eléctrico", 4, "FUS-KIT1", "Kit de fusibles automotrices", 45, 80, 25, 8),
    ("Suspensión", 6, "AMO-DEL2", "Amortiguador delantero Chevrolet Aveo", 620, 850, 4, 2), ("Suspensión", 6, "AMO-TRA2", "Amortiguador trasero Nissan Versa", 480, 690, 5, 2),
    ("Suspensión", 6, "RES-001", "Resorte de suspensión delantero", 700, 980, 3, 2), ("Suspensión", 6, "BUJ-SUS1", "Buje de barra estabilizadora", 60, 105, 20, 6),
    ("Suspensión", 6, "ROT-SUP1", "Rótula de suspensión superior", 210, 330, 8, 3), ("Suspensión", 6, "TOP-001", "Soporte de amortiguador (cazoleta)", 250, 380, 6, 2),
    ("Dirección", 6, "TER-DIR1", "Terminal de dirección exterior", 180, 280, 10, 4), ("Dirección", 6, "TER-DIR2", "Terminal de dirección interior", 160, 255, 8, 4),
    ("Dirección", 6, "CRE-001", "Cremallera de dirección reconstruida", 2400, 3350, 1, 1), ("Dirección", 6, "BOM-DIR1", "Bomba de dirección hidráulica", 1800, 2520, 1, 1),
    ("Llantas", 5, "LLA-195", "Llanta 195/55 R16", 1250, 1680, 8, 4), ("Llantas", 5, "LLA-205", "Llanta 205/60 R16", 1400, 1890, 6, 4),
    ("Llantas", 5, "LLA-225", "Llanta 225/65 R17", 1850, 2490, 4, 4), ("Llantas", 5, "LLA-LT1", "Llanta 245/75 R16 de carga", 2300, 3100, 5, 4),
    ("Llantas", 5, "RIN-15", "Rin de acero 15\"", 520, 780, 6, 2), ("Llantas", 5, "VAL-001", "Válvula de llanta (juego de 4)", 30, 60, 30, 10),
    ("Bandas y mangueras", 2, "BAN-SER2", "Banda de accesorios Chevrolet Aveo", 140, 215, 8, 3), ("Bandas y mangueras", 2, "BAN-DIS1", "Banda de distribución con tensor", 620, 890, 4, 2),
    ("Bandas y mangueras", 2, "MAN-RAD1", "Manguera superior de radiador", 160, 255, 6, 3), ("Bandas y mangueras", 2, "MAN-RAD2", "Manguera inferior de radiador", 150, 240, 5, 3),
    ("Refrigeración", 2, "RAD-001", "Radiador de aluminio universal", 1650, 2290, 2, 1), ("Refrigeración", 2, "TER-001", "Termostato con empaque", 120, 195, 9, 3),
    ("Refrigeración", 2, "BOM-AGU1", "Bomba de agua", 480, 710, 4, 2), ("Refrigeración", 2, "TAP-RAD1", "Tapón de radiador", 40, 75, 15, 5),
    ("Transmisión", 6, "CLU-001", "Kit de clutch (disco, plato y collarín)", 1800, 2560, 2, 1), ("Transmisión", 6, "JUN-HOM1", "Junta homocinética", 520, 780, 4, 2),
    ("Transmisión", 6, "BAL-RUE1", "Balero de rueda delantero", 260, 400, 7, 3), ("Accesorios", 1, "LIM-PAR1", "Limpiaparabrisas (par)", 80, 140, 16, 6),
    ("Accesorios", 1, "TAP-GAS1", "Tapón de gasolina", 55, 95, 10, 3), ("Accesorios", 1, "TAP-HUL1", "Tapetes de hule universales (juego)", 160, 260, 8, 3)]

# Servicio -> productos que normalmente consume (código, cantidad); se usa para armar órdenes y ventas creíbles
COMBOS = {"Cambio de aceite": [("ACE-5W30", 4), ("FIL-ACE1", 1)], "Cambio de balatas": [("BAL-001", 1)],
          "Afinación general": [("BUJ-NGK4", 1), ("FIL-AIR1", 1), ("FIL-ACE1", 1)], "Cambio de filtro de aire": [("FIL-AIR2", 1)],
          "Cambio de banda de accesorios": [("BAN-SER1", 1)], "Cambio de batería": [("BAT-35", 1)],
          "Cambio de amortiguadores (por eje)": [("AMO-DEL2", 2)], "Cambio de anticongelante": [("ANT-50-1", 1)],
          "Cambio de discos de freno": [("DIS-DEL1", 2)], "Servicio de frenos completo": [("BAL-002", 1), ("LIQ-FRE1", 1)]}


def cargar(conn):
    cur = conn.cursor()
    cur.execute("SELECT count(*) AS n FROM usuario")
    if cur.fetchone()["n"]:
        print("La base ya tiene datos; no se cargó nada (para empezar de cero, recree la base y ejecute aivac_schema.sql).")
        return False
    rnd = random.Random(2026)
    hash_demo = generate_password_hash(CONTRASENA_DEMO)
    for rol, nombre, usuario in USUARIOS:
        cur.execute("""INSERT INTO usuario (id_rol, nombre_completo, nombre_usuario, contrasena_hash)
                       SELECT id_rol, %s, %s, %s FROM rol WHERE nombre = %s""", (nombre, usuario, hash_demo, rol))
    for nombre, tipo, tel, correo in CLIENTES:
        cur.execute("INSERT INTO cliente (nombre, tipo_cliente, telefono, correo) VALUES (%s,%s,%s,%s)", (nombre, tipo, tel, correo))
    for cli, placas, marca, modelo, anio, uso, km in VEHICULOS:
        cur.execute("""INSERT INTO vehiculo (id_cliente, placas, marca, modelo, anio, tipo_uso, kilometraje_actual)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""", (cli, placas, marca, modelo, anio, uso, km))
    for nombre, tel in PROVEEDORES:
        cur.execute("INSERT INTO proveedor (nombre, telefono) VALUES (%s,%s)", (nombre, tel))
    for c in CATEGORIAS_EXTRA:
        cur.execute("INSERT INTO categoria (nombre) SELECT %s WHERE NOT EXISTS (SELECT 1 FROM categoria WHERE nombre = %s)", (c, c))
    for nombre, precio in SERVICIOS_EXTRA:
        cur.execute("INSERT INTO servicio (nombre, precio_base) SELECT %s, %s WHERE NOT EXISTS (SELECT 1 FROM servicio WHERE nombre = %s)", (nombre, precio, nombre))

    # Catálogo: se crea con stock 0; las existencias se alcanzan con movimientos para que la bitácora cuadre
    for cat, prov, cod, nom, comp, vta, stock, minimo in PRODUCTOS:
        cur.execute("""INSERT INTO producto (id_categoria, id_proveedor, codigo, nombre, precio_compra, precio_venta, stock_actual, stock_minimo)
                       SELECT id_categoria, %s, %s, %s, %s, %s, 0, %s FROM categoria WHERE nombre = %s""", (prov, cod, nom, comp, vta, minimo, cat))
    fichas.completar(conn, confirmar=False)
    cur.execute("SELECT id_producto, codigo, precio_venta FROM producto")
    prod = {r["codigo"]: r for r in cur.fetchall()}
    cur.execute("SELECT id_servicio, nombre, precio_base FROM servicio")
    serv = {r["nombre"]: r for r in cur.fetchall()}
    cur.execute("SELECT id_usuario, nombre_usuario FROM usuario")
    uid = {r["nombre_usuario"]: r["id_usuario"] for r in cur.fetchall()}
    cur.execute("SELECT id_cliente, id_vehiculo, kilometraje_actual FROM vehiculo ORDER BY id_vehiculo")
    vehs = cur.fetchall()
    destino = {p[2]: p[6] for p in PRODUCTOS}   # stock final deseado
    vendido = {c: 0 for c in destino}            # salidas históricas por producto

    # ------------------------------------------------------------------ ventas históricas (últimos 60 días)
    codigos_venta = ["ACE-5W30", "ACE-10W40", "FIL-ACE1", "FIL-AIR1", "FIL-COM1", "BAL-001", "BAL-002", "BAL-003", "FOC-H4", "LIM-PAR1",
                     "LIQ-FRE1", "BUJ-NGK4", "BAT-35", "ANT-50-1", "VAL-001", "GRA-MP1", "FUS-KIT1", "TAP-RAD1", "FIL-CAB1"]
    ventas = []
    for i in range(46):
        fecha = AHORA - timedelta(days=rnd.randint(1, 60), hours=rnd.randint(0, 8), minutes=rnd.randint(0, 59))
        cliente = rnd.choice([None, None] + [v["id_cliente"] for v in vehs])
        usuario = uid[rnd.choice(["gerente.admin", "refacciones"])]
        partidas = []
        for cod in rnd.sample(codigos_venta, rnd.randint(1, 3)):
            partidas.append(("producto", cod, rnd.randint(1, 3)))
        if rnd.random() < .45:
            partidas.append(("servicio", rnd.choice(["Alineación", "Balanceo computarizado", "Cambio de aceite", "Rotación de llantas"]), 1))
        ventas.append((fecha, cliente, usuario, rnd.choice(["efectivo", "efectivo", "tarjeta", "tarjeta", "transferencia", "credito"]), partidas))
    ventas.sort(key=lambda v: v[0])

    # ------------------------------------------------------------------ órdenes de trabajo históricas
    ordenes = []
    vlist = list(vehs)
    rnd.shuffle(vlist)
    plan = ["entregada"] * 9 + ["terminada"] * 2 + ["en_proceso"] * 2 + ["abierta"] * 2 + ["cancelada"]
    for estatus, v in zip(plan, vlist):
        dias = {"entregada": rnd.randint(8, 55), "terminada": rnd.randint(1, 3), "en_proceso": rnd.randint(0, 2),
                "abierta": 0, "cancelada": rnd.randint(5, 30)}[estatus]
        ingreso = AHORA - timedelta(days=dias, hours=rnd.randint(0, 5))
        nombres = rnd.sample(list(COMBOS), rnd.randint(1, 2)) + (["Alineación"] if rnd.random() < .5 else [])
        ordenes.append({"veh": v, "mec": uid[rnd.choice(["mecanico1", "mecanico2", "mecanico3"])], "ingreso": ingreso, "estatus": estatus,
                        "km": v["kilometraje_actual"] - (rnd.randint(300, 9000) if estatus == "entregada" else 0), "servicios": nombres,
                        "obs": rnd.choice(["Cambio por mantenimiento programado.", "Ruido al frenar.", "Revisión general antes de viaje.",
                                           "Vibración al manejar a más de 80 km/h.", "Luz de aceite encendida.", "Falla al arrancar en frío."])})
    # Lo surtido a órdenes y vendido se suma a la compra inicial, así el stock final siempre es el del catálogo
    for o in ordenes:
        o["refs"] = [(cod, n) for s in o["servicios"] for cod, n in COMBOS.get(s, [])] if o["estatus"] != "abierta" else []
        for cod, n in o["refs"]:
            if o["estatus"] != "cancelada":
                vendido[cod] += n
    for f, cl, us, fp, partidas in ventas:
        for t, k, n in partidas:
            if t == "producto":
                vendido[k] += n

    # Compra inicial: stock final + todo lo vendido/surtido, fechada antes de la primera salida
    for cat, prov, cod, nom, comp, vta, stock, minimo in PRODUCTOS:
        total_entrada = stock + vendido[cod]
        if total_entrada:
            cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, fecha, referencia)
                           VALUES (%s,%s,'entrada',%s,%s,'COMPRA-INICIAL')""", (prod[cod]["id_producto"], uid["refacciones"], total_entrada, AHORA - timedelta(days=75)))

    for f, cl, us, fp, partidas in ventas:
        cur.execute("INSERT INTO venta (id_cliente, id_usuario, fecha, forma_pago) VALUES (%s,%s,%s,%s) RETURNING id_venta", (cl, us, f, fp))
        idv = cur.fetchone()["id_venta"]
        for t, k, n in partidas:
            if t == "producto":
                p = prod[k]
                cur.execute("INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario) VALUES (%s,%s,%s,%s)", (idv, p["id_producto"], n, p["precio_venta"]))
                cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, fecha, referencia)
                               VALUES (%s,%s,'salida',%s,%s,%s)""", (p["id_producto"], us, n, f, "VENTA-%d" % idv))
            else:
                s = serv[k]
                cur.execute("INSERT INTO detalle_venta (id_venta, id_servicio, cantidad, precio_unitario) VALUES (%s,%s,1,%s)", (idv, s["id_servicio"], s["precio_base"]))

    for o in sorted(ordenes, key=lambda x: x["ingreso"]):
        entrega = o["ingreso"] + timedelta(days=rnd.randint(0, 2), hours=4) if o["estatus"] == "entregada" else None
        cur.execute("""INSERT INTO orden_trabajo (id_vehiculo, id_mecanico, fecha_ingreso, fecha_entrega, kilometraje_ingreso, estatus, observaciones)
                       VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id_orden""",
                    (o["veh"]["id_vehiculo"], o["mec"], o["ingreso"], entrega, o["km"], o["estatus"], o["obs"]))
        ido = cur.fetchone()["id_orden"]
        for s in o["servicios"]:
            cur.execute("INSERT INTO detalle_orden_servicio (id_orden, id_servicio, precio_aplicado) VALUES (%s,%s,%s)", (ido, serv[s]["id_servicio"], serv[s]["precio_base"]))
        for cod, n in o["refs"]:
            surtida = o["estatus"] != "cancelada"
            cur.execute("INSERT INTO solicitud_refaccion (id_orden, id_producto, cantidad, fecha_solicitud, estatus) VALUES (%s,%s,%s,%s,%s)",
                        (ido, prod[cod]["id_producto"], n, o["ingreso"], "surtida" if surtida else "cancelada"))
            if surtida:
                cur.execute("""INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad, fecha, referencia)
                               VALUES (%s,%s,'salida',%s,%s,%s)""", (prod[cod]["id_producto"], o["mec"], n, o["ingreso"], "ORDEN-%d" % ido))

    # ------------------------------------------------------------------ seguimiento de componentes (semáforo de desgaste)
    cur.execute("SELECT id_componente, nombre, intervalo_km, intervalo_dias FROM componente WHERE nombre IN ('Aceite de motor','Balatas','Bujías')")
    comps = cur.fetchall()
    for v in vehs:
        for c in comps:
            km_desde = int(c["intervalo_km"] * rnd.choice([.15, .35, .55, .75, .95]))
            dias = int(c["intervalo_dias"] * rnd.choice([.1, .3, .5, .7, .9]))
            cur.execute("""INSERT INTO seguimiento_componente (id_vehiculo, id_componente, km_ultimo_servicio, fecha_ultimo_servicio)
                           VALUES (%s,%s,%s,%s)""", (v["id_vehiculo"], c["id_componente"], max(0, v["kilometraje_actual"] - km_desde), (AHORA - timedelta(days=dias)).date()))
    conn.commit()
    return True


if __name__ == "__main__":
    c = db.conectar()
    if cargar(c):
        print("Datos demo cargados: %d usuarios, %d clientes, %d vehículos, %d refacciones." % (len(USUARIOS), len(CLIENTES), len(VEHICULOS), len(PRODUCTOS)))
    c.close()
