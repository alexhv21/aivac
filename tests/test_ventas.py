"""Pruebas unitarias y de integración de la lógica de ventas (Sprint 2).
Se ejecutan contra una base de datos PostgreSQL real (variable AIVAC_DSN)."""
import unittest
from decimal import Decimal

import soporte
import ventas

ID_BALATAS, ID_ACEITE, ID_SIN_EXISTENCIA, ID_CAMBIO_BALATAS = 1, 3, 7, 6  # claves de los datos demo
ID_USUARIO = 2  # Gerente Administrativa (demo)


def setUpModule():
    soporte.guardar_stock_inicial()


class PruebasVentas(unittest.TestCase):
    def setUp(self):
        soporte.restaurar()
        self.c = soporte.conn(); self.cur = self.c.cursor()

    def tearDown(self):
        self.c.close()

    def vender(self, partidas, pago="efectivo", cliente=None):
        return ventas.registrar_venta(self.c, ID_USUARIO, cliente, pago, partidas)

    def test_01_venta_descuenta_stock(self):
        antes = soporte.stock(self.cur, "BAL-001")
        self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": 2}])
        self.assertEqual(soporte.stock(self.cur, "BAL-001"), antes - 2)

    def test_02_registra_movimiento_de_salida(self):
        idv = self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": 1}])
        self.cur.execute("SELECT tipo, cantidad, referencia FROM movimiento_inventario")
        m = self.cur.fetchall()
        self.assertEqual(len(m), 1)
        self.assertEqual((m[0]["tipo"], m[0]["cantidad"], m[0]["referencia"]), ("salida", 1, "VENTA-%d" % idv))

    def test_03_total_calculado_con_precios_de_la_bd(self):
        idv = self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": 2}, {"tipo": "producto", "id": ID_ACEITE, "cantidad": 4}])
        _, _, total = ventas.comprobante(self.cur, idv)
        self.assertEqual(total, Decimal("520") * 2 + Decimal("165") * 4)

    def test_04_venta_mixta_servicio_no_mueve_inventario(self):
        self.vender([{"tipo": "servicio", "id": ID_CAMBIO_BALATAS, "cantidad": 1}, {"tipo": "producto", "id": ID_BALATAS, "cantidad": 1}])
        self.cur.execute("SELECT count(*) AS n FROM movimiento_inventario")
        self.assertEqual(self.cur.fetchone()["n"], 1)

    def test_05_sin_existencia_se_rechaza_sin_cambios(self):
        with self.assertRaises(ventas.VentaError) as cm:
            self.vender([{"tipo": "producto", "id": ID_SIN_EXISTENCIA, "cantidad": 1}])
        self.assertIn("Sin existencia", str(cm.exception))
        self.cur.execute("SELECT count(*) AS n FROM venta")
        self.assertEqual(self.cur.fetchone()["n"], 0)

    def test_06_atomicidad_una_partida_invalida_revierte_todo(self):
        antes = soporte.stock(self.cur, "BAL-001")
        with self.assertRaises(ventas.VentaError):
            self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": 1}, {"tipo": "producto", "id": ID_SIN_EXISTENCIA, "cantidad": 1}])
        self.cur.execute("SELECT count(*) AS n FROM venta")
        self.assertEqual(self.cur.fetchone()["n"], 0)
        self.assertEqual(soporte.stock(self.cur, "BAL-001"), antes)

    def test_07_forma_de_pago_invalida(self):
        with self.assertRaises(ventas.VentaError):
            self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": 1}], pago="cheque")

    def test_08_venta_sin_partidas(self):
        with self.assertRaises(ventas.VentaError):
            self.vender([])

    def test_09_cantidad_cero_o_negativa(self):
        for cant in (0, -3):
            with self.assertRaises(ventas.VentaError):
                self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": cant}])

    def test_10_cliente_opcional(self):
        a = self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": 1}])
        b = self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": 1}], cliente=1)
        self.assertEqual(ventas.comprobante(self.cur, a)[0]["cliente"], "Venta de mostrador")
        self.assertEqual(ventas.comprobante(self.cur, b)[0]["cliente"], "Juan Pérez Demo")

    def test_11_no_se_puede_vender_mas_que_la_existencia(self):
        disponible = soporte.stock(self.cur, "BAL-001")
        with self.assertRaises(ventas.VentaError):
            self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": disponible + 1}])
        self.vender([{"tipo": "producto", "id": ID_BALATAS, "cantidad": disponible}])  # exactamente la existencia sí se permite
        self.assertEqual(soporte.stock(self.cur, "BAL-001"), 0)

    def test_12_busqueda_de_catalogo_por_codigo_y_nombre(self):
        self.assertEqual(ventas.buscar_catalogo(self.cur, "BAL-001")[0]["id"], ID_BALATAS)
        nombres = [r["nombre"] for r in ventas.buscar_catalogo(self.cur, "aceite")]
        self.assertTrue(any("Aceite" in n for n in nombres) and any("aceite" in n.lower() for n in nombres))

    def test_13_busqueda_de_clientes_por_placas(self):
        r = ventas.buscar_clientes(self.cur, "OAX-908")
        self.assertEqual([x["nombre"] for x in r], ["Transportes Ejemplo S.A."])


if __name__ == "__main__":
    unittest.main(verbosity=2)
