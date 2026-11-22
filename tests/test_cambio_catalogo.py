"""Pruebas del cambio en efectivo y del catálogo de refacciones (lógica y rutas web)."""
import unittest
from decimal import Decimal

import catalogo
import soporte
import ventas
from app import crear_app

CLAVE = "Demo2026!"


def setUpModule():
    soporte.guardar_stock_inicial()


class _Base(unittest.TestCase):
    def setUp(self):
        soporte.restaurar()
        self.conn = soporte.conn(); self.cur = self.conn.cursor()
        self.cur.execute("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'gerente.admin'")
        self.uid = self.cur.fetchone()["id_usuario"]
        self.cur.execute("SELECT id_producto FROM producto WHERE codigo = 'BAL-001'")
        self.bal = self.cur.fetchone()["id_producto"]

    def tearDown(self):
        self.conn.close()


class PruebasCambio(_Base):
    def _venta(self, recibido, forma="efectivo"):
        return ventas.registrar_venta(self.conn, self.uid, None, forma, [{"tipo": "producto", "id": self.bal, "cantidad": 2}], recibido)

    def test_01_cambio_correcto(self):
        v = self._venta("1500")          # total 2 x 520 = 1040
        cab = ventas.comprobante(self.cur, v)[0]
        self.assertEqual((cab["monto_recibido"], cab["cambio"]), (Decimal("1500.00"), Decimal("460.00")))

    def test_02_pago_exacto_da_cambio_cero(self):
        cab = ventas.comprobante(self.cur, self._venta("1040"))[0]
        self.assertEqual(cab["cambio"], Decimal("0.00"))

    def test_03_efectivo_insuficiente_se_rechaza_y_no_deja_venta_ni_baja_stock(self):
        antes = soporte.stock(self.cur, "BAL-001")
        with self.assertRaises(ventas.VentaError) as e:
            self._venta("1000")
        self.assertIn("no cubre el total", str(e.exception))
        self.conn.rollback()
        self.assertEqual(soporte.stock(self.cur, "BAL-001"), antes)
        self.cur.execute("SELECT count(*) AS n FROM venta"); self.assertEqual(self.cur.fetchone()["n"], 0)

    def test_04_importe_no_numerico_se_rechaza(self):
        with self.assertRaises(ventas.VentaError):
            self._venta("abc")

    def test_05_tarjeta_no_guarda_efectivo_ni_cambio(self):
        cab = ventas.comprobante(self.cur, self._venta("5000", "tarjeta"))[0]
        self.assertIsNone(cab["monto_recibido"]); self.assertIsNone(cab["cambio"])


class PruebasCatalogo(_Base):
    def _datos(self, **kw):
        d = {"codigo": "tst-001", "nombre": "TEST Pieza", "id_categoria": 1, "precio_compra": "100", "precio_venta": "150",
             "stock_minimo": "2", "stock_inicial": "7", "marca": "Marca X", "descripcion": "Características de prueba", "ubicacion": "Estante Z-9"}
        d.update(kw); return d

    def test_06_alta_con_existencia_inicial_deja_entrada_en_bitacora(self):
        idp = catalogo.guardar(self.conn, self.uid, self._datos())
        p = catalogo.obtener(self.cur, idp)
        self.assertEqual((p["codigo"], p["stock_actual"], float(p["utilidad"]), float(p["margen_pct"])), ("TST-001", 7, 50.0, 50.0))
        self.assertEqual(catalogo.movimientos(self.cur, idp)[0]["referencia"], "ALTA-INICIAL")

    def test_07_codigo_duplicado_se_rechaza(self):
        catalogo.guardar(self.conn, self.uid, self._datos())
        with self.assertRaises(catalogo.CatalogoError):
            catalogo.guardar(self.conn, self.uid, self._datos(nombre="Otra"))

    def test_08_precio_invalido_y_faltantes_se_rechazan(self):
        for malo in (self._datos(precio_venta="-5"), self._datos(precio_venta="abc"), self._datos(nombre=""), self._datos(id_categoria="")):
            with self.assertRaises(catalogo.CatalogoError):
                catalogo.guardar(self.conn, self.uid, malo)

    def test_09_editar_no_cambia_la_existencia(self):
        idp = catalogo.guardar(self.conn, self.uid, self._datos())
        catalogo.guardar(self.conn, self.uid, self._datos(precio_venta="200", stock_inicial="99"), idp)
        p = catalogo.obtener(self.cur, idp)
        self.assertEqual((float(p["precio_venta"]), p["stock_actual"]), (200.0, 7))

    def test_10_entrada_suma_existencia(self):
        antes = soporte.stock(self.cur, "BAL-001")
        catalogo.registrar_entrada(self.conn, self.uid, self.bal, 5, "compra")
        self.conn.rollback()
        self.assertEqual(soporte.stock(self.cur, "BAL-001"), antes + 5)

    def test_11_entrada_invalida_se_rechaza(self):
        for n in (0, -3, "x"):
            with self.assertRaises(catalogo.CatalogoError):
                catalogo.registrar_entrada(self.conn, self.uid, self.bal, n)

    def test_12_busqueda_por_compatibilidad_y_marca(self):
        self.assertTrue(any(r["codigo"] == "BAL-001" for r in catalogo.listar(self.cur, "Versa")))
        self.assertEqual(catalogo.listar(self.cur, "zzzz-no-existe"), [])


class PruebasRutas(unittest.TestCase):
    def setUp(self):
        soporte.restaurar()
        self.cli = crear_app().test_client()

    def entrar(self, u):
        self.cli.post("/login", data={"usuario": u, "contrasena": CLAVE})

    def test_13_post_venta_efectivo_sin_monto_devuelve_422(self):
        self.entrar("gerente.admin")
        c = soporte.conn(); cur = c.cursor(); cur.execute("SELECT id_producto FROM producto WHERE codigo='BAL-001'"); p = cur.fetchone()["id_producto"]; c.close()
        r = self.cli.post("/ventas", json={"forma_pago": "efectivo", "partidas": [{"tipo": "producto", "id": p, "cantidad": 1}]})
        self.assertEqual(r.status_code, 422); self.assertIn("efectivo", r.get_json()["error"])

    def test_14_comprobante_muestra_recibido_y_cambio(self):
        self.entrar("gerente.admin")
        c = soporte.conn(); cur = c.cursor(); cur.execute("SELECT id_producto FROM producto WHERE codigo='BAL-001'"); p = cur.fetchone()["id_producto"]; c.close()
        r = self.cli.post("/ventas", json={"forma_pago": "efectivo", "monto_recibido": "600", "partidas": [{"tipo": "producto", "id": p, "cantidad": 1}]})
        self.assertEqual(r.status_code, 200)
        pag = self.cli.get(r.get_json()["url"]).get_data(as_text=True)
        self.assertIn("$600.00", pag); self.assertIn("$80.00", pag); self.assertIn("Cambio", pag)

    def test_15_catalogo_alta_por_web_y_ficha(self):
        self.entrar("refacciones")
        r = self.cli.post("/refacciones/nueva", data={"codigo": "TST-W1", "nombre": "TEST Web", "id_categoria": 1, "precio_venta": "99", "stock_inicial": "3"})
        self.assertEqual(r.status_code, 302)
        pag = self.cli.get(r.headers["Location"]).get_data(as_text=True)
        self.assertIn("TST-W1", pag); self.assertIn("$99.00", pag); self.assertIn("ALTA-INICIAL", pag)

    def test_16_mecanico_no_entra_al_catalogo(self):
        self.entrar("mecanico1")
        self.assertEqual(self.cli.get("/refacciones").status_code, 403)

    def test_17_refaccion_inexistente_da_404(self):
        self.entrar("gerente.admin")
        self.assertEqual(self.cli.get("/refacciones/99999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
