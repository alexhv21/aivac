"""Pruebas de la lógica de clientes, vehículos y órdenes de trabajo (Sprint 3) contra PostgreSQL."""
import unittest

import soporte
import taller


def setUpModule():
    soporte.guardar_stock_inicial()


class PruebasTaller(unittest.TestCase):
    def setUp(self):
        soporte.restaurar()
        self.conn = soporte.conn()
        self.cur = self.conn.cursor()
        self.cur.execute("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'mecanico1'")
        self.mec = self.cur.fetchone()["id_usuario"]
        self.cur.execute("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'gerente.admin'")
        self.ger = self.cur.fetchone()["id_usuario"]
        self.cli = taller.guardar_cliente(self.conn, {"nombre": "TEST Cliente", "tipo_cliente": "particular", "telefono": "9510000000"})
        self.veh = taller.guardar_vehiculo(self.conn, {"id_cliente": self.cli, "placas": "tst-001", "marca": "Nissan", "modelo": "Versa",
                                                         "anio": 2018, "kilometraje_actual": 50000})

    def tearDown(self):
        self.conn.close()

    def _orden(self):
        return taller.crear_orden(self.conn, self.veh, self.mec, 50500, "Prueba")

    def _servicio(self, nombre):
        self.cur.execute("SELECT id_servicio FROM servicio WHERE nombre = %s", (nombre,))
        return self.cur.fetchone()["id_servicio"]

    def _producto(self, codigo):
        self.cur.execute("SELECT id_producto FROM producto WHERE codigo = %s", (codigo,))
        return self.cur.fetchone()["id_producto"]

    # ---- clientes
    def test_01_cliente_valido_se_guarda(self):
        self.assertEqual(taller.obtener_cliente(self.cur, self.cli)["nombre"], "TEST Cliente")

    def test_02_cliente_sin_nombre_se_rechaza(self):
        with self.assertRaises(taller.TallerError):
            taller.guardar_cliente(self.conn, {"nombre": "  ", "tipo_cliente": "particular"})

    def test_03_telefono_invalido_se_rechaza(self):
        with self.assertRaises(taller.TallerError) as e:
            taller.guardar_cliente(self.conn, {"nombre": "TEST X", "tipo_cliente": "particular", "telefono": "123"})
        self.assertIn("10 dígitos", str(e.exception))

    def test_04_correo_invalido_se_rechaza(self):
        with self.assertRaises(taller.TallerError):
            taller.guardar_cliente(self.conn, {"nombre": "TEST X", "tipo_cliente": "particular", "correo": "sin-arroba"})

    def test_05_buscar_cliente_por_nombre(self):
        self.assertEqual([c["nombre"] for c in taller.listar_clientes(self.cur, "test cli")], ["TEST Cliente"])

    # ---- vehículos
    def test_06_placas_se_guardan_en_mayusculas(self):
        self.assertEqual(taller.obtener_vehiculo(self.cur, self.veh)["placas"], "TST-001")

    def test_07_placas_duplicadas_se_rechazan(self):
        with self.assertRaises(taller.TallerError) as e:
            taller.guardar_vehiculo(self.conn, {"id_cliente": self.cli, "placas": "TST-001"})
        self.assertIn("Ya existe", str(e.exception))

    def test_08_anio_fuera_de_rango_se_rechaza(self):
        with self.assertRaises(taller.TallerError):
            taller.guardar_vehiculo(self.conn, {"id_cliente": self.cli, "placas": "TST-002", "anio": 1800})

    # ---- órdenes
    def test_09_crear_orden(self):
        o = self._orden()
        self.assertEqual(taller.obtener_orden(self.cur, o)[0]["estatus"], "abierta")

    def test_10_no_se_abren_dos_ordenes_para_el_mismo_vehiculo(self):
        self._orden()
        with self.assertRaises(taller.TallerError) as e:
            self._orden()
        self.assertIn("ya tiene la orden abierta", str(e.exception))

    def test_11_kilometraje_menor_al_registrado_se_rechaza(self):
        with self.assertRaises(taller.TallerError):
            taller.crear_orden(self.conn, self.veh, self.mec, 100, "")

    def test_12_servicio_y_total(self):
        o = self._orden()
        taller.agregar_servicio(self.conn, o, self._servicio("Alineación"))
        taller.agregar_servicio(self.conn, o, self._servicio("Cambio de aceite"))
        self.assertEqual(float(taller.obtener_orden(self.cur, o)[3]), 550.0)

    def test_13_servicio_repetido_se_rechaza(self):
        o = self._orden(); s = self._servicio("Alineación")
        taller.agregar_servicio(self.conn, o, s)
        with self.assertRaises(taller.TallerError):
            taller.agregar_servicio(self.conn, o, s)

    def test_14_refaccion_surtida_descuenta_stock(self):
        o = self._orden(); antes = soporte.stock(self.cur, "BAL-001")
        self.assertEqual(taller.solicitar_refaccion(self.conn, self.mec, o, self._producto("BAL-001"), 2), "surtida")
        self.conn.rollback()
        self.assertEqual(soporte.stock(self.cur, "BAL-001"), antes - 2)
        self.assertEqual(float(taller.obtener_orden(self.cur, o)[3]), 1040.0)

    def test_15_refaccion_sin_existencia_queda_registrada_sin_mover_stock(self):
        o = self._orden()
        self.assertEqual(taller.solicitar_refaccion(self.conn, self.mec, o, self._producto("AMO-TRA1"), 1), "sin_existencia")
        self.conn.rollback()
        self.assertEqual(soporte.stock(self.cur, "AMO-TRA1"), 0)
        self.assertEqual(taller.obtener_orden(self.cur, o)[2][0]["estatus"], "sin_existencia")
        self.assertEqual(float(taller.obtener_orden(self.cur, o)[3]), 0.0)

    def test_16_transicion_invalida_se_rechaza(self):
        o = self._orden()
        with self.assertRaises(taller.TallerError):
            taller.cambiar_estatus(self.conn, self.mec, o, "entregada")

    def test_17_entregar_registra_fecha_y_actualiza_km(self):
        o = self._orden()
        for e in ("en_proceso", "terminada", "entregada"):
            taller.cambiar_estatus(self.conn, self.mec, o, e)
        cab = taller.obtener_orden(self.cur, o)[0]
        self.assertIsNotNone(cab["fecha_entrega"])
        self.assertEqual(taller.obtener_vehiculo(self.cur, self.veh)["kilometraje_actual"], 50500)

    def test_18_cancelar_devuelve_refacciones_al_inventario(self):
        o = self._orden(); antes = soporte.stock(self.cur, "BAL-001")
        taller.solicitar_refaccion(self.conn, self.mec, o, self._producto("BAL-001"), 3)
        taller.cambiar_estatus(self.conn, self.ger, o, "cancelada")
        self.conn.rollback()
        self.assertEqual(soporte.stock(self.cur, "BAL-001"), antes)

    def test_19_orden_entregada_no_admite_cambios(self):
        o = self._orden()
        for e in ("en_proceso", "terminada", "entregada"):
            taller.cambiar_estatus(self.conn, self.mec, o, e)
        with self.assertRaises(taller.TallerError):
            taller.agregar_servicio(self.conn, o, self._servicio("Alineación"))

    def test_20_solicitud_atomica_si_la_refaccion_no_existe(self):
        o = self._orden()
        with self.assertRaises(taller.TallerError):
            taller.solicitar_refaccion(self.conn, self.mec, o, 99999, 1)
        self.conn.rollback()
        self.assertEqual(taller.obtener_orden(self.cur, o)[2], [])


if __name__ == "__main__":
    unittest.main()
