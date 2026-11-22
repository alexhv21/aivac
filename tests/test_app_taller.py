"""Pruebas de las rutas web de clientes, vehículos y órdenes de trabajo (sesión y permisos por rol)."""
import unittest

import soporte
import taller
from app import crear_app

CLAVE = "Demo2026!"


def setUpModule():
    soporte.guardar_stock_inicial()


class PruebasAppTaller(unittest.TestCase):
    def setUp(self):
        soporte.restaurar()
        self.cli = crear_app().test_client()

    def entrar(self, usuario):
        return self.cli.post("/login", data={"usuario": usuario, "contrasena": CLAVE})

    def _datos(self):
        c = soporte.conn(); cur = c.cursor()
        cur.execute("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'mecanico1'"); m1 = cur.fetchone()["id_usuario"]
        cur.execute("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'mecanico2'"); m2 = cur.fetchone()["id_usuario"]
        cur.execute("SELECT id_vehiculo FROM vehiculo WHERE placas = 'OAX-123'"); v1 = cur.fetchone()["id_vehiculo"]
        cur.execute("SELECT id_vehiculo FROM vehiculo WHERE placas = 'OAX-555'"); v2 = cur.fetchone()["id_vehiculo"]
        cur.execute("SELECT id_cliente FROM cliente WHERE nombre = 'Juan Pérez Demo'"); cl = cur.fetchone()["id_cliente"]
        c.close()
        return m1, m2, v1, v2, cl

    def test_01_gerente_crea_cliente_y_aparece_en_la_lista(self):
        self.entrar("gerente.admin")
        r = self.cli.post("/clientes/nuevo", data={"nombre": "TEST Web", "tipo_cliente": "particular", "telefono": "9511112222"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("TEST Web", self.cli.get("/clientes?q=TEST+Web").get_data(as_text=True))

    def test_02_cliente_invalido_muestra_el_error_y_no_guarda(self):
        self.entrar("gerente.admin")
        r = self.cli.post("/clientes/nuevo", data={"nombre": "TEST Mal", "tipo_cliente": "particular", "telefono": "12"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("10 dígitos", r.get_data(as_text=True))
        self.assertIn("No se encontraron clientes", self.cli.get("/clientes?q=TEST+Mal").get_data(as_text=True))

    def test_03_mecanico_no_entra_a_clientes(self):
        self.entrar("mecanico1")
        self.assertEqual(self.cli.get("/clientes").status_code, 403)
        self.assertEqual(self.cli.get("/vehiculos").status_code, 403)

    def test_04_sin_sesion_redirige_al_login(self):
        self.assertEqual(self.cli.get("/ordenes").status_code, 302)
        self.assertEqual(self.cli.post("/ordenes/1/estatus", data={"estatus": "en_proceso"}).status_code, 302)

    def test_05_mecanico_inicia_en_sus_ordenes(self):
        self.entrar("mecanico1")
        r = self.cli.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/ordenes"))

    def test_06_flujo_de_orden_por_web(self):
        m1, m2, v1, v2, cl = self._datos()
        self.entrar("gerente.admin")
        c = soporte.conn(); cur = c.cursor()
        cur.execute("DELETE FROM orden_trabajo WHERE id_vehiculo = %s", (v1,))  # los datos demo ya traen órdenes; se libera el vehículo
        c.commit()
        r = self.cli.post("/ordenes/nueva", data={"id_vehiculo": v1, "id_mecanico": m1, "kilometraje": 49000, "observaciones": "Ruido"})
        self.assertEqual(r.status_code, 302)
        url = r.headers["Location"]
        cur.execute("SELECT id_servicio FROM servicio WHERE nombre = 'Alineación'"); s = cur.fetchone()["id_servicio"]
        cur.execute("SELECT id_producto FROM producto WHERE codigo = 'BAL-001'"); p = cur.fetchone()["id_producto"]
        antes = soporte.stock(cur, "BAL-001")
        self.cli.post(url + "/servicio", data={"id_servicio": s})
        self.cli.post(url + "/refaccion", data={"id_producto": p, "cantidad": 1})
        pag = self.cli.get(url).get_data(as_text=True)
        self.assertIn("Alineación", pag); self.assertIn("BAL-001", pag); self.assertIn("$870.00", pag)
        c.rollback(); self.assertEqual(soporte.stock(cur, "BAL-001"), antes - 1)
        self.cli.post(url + "/estatus", data={"estatus": "en_proceso"})
        self.assertIn("En proceso", self.cli.get(url).get_data(as_text=True))
        c.close()

    def test_07_mecanico_solo_ve_sus_ordenes(self):
        m1, m2, v1, v2, cl = self._datos()
        c = soporte.conn(); cur = c.cursor()
        cur.execute("DELETE FROM orden_trabajo WHERE id_vehiculo IN (%s, %s)", (v1, v2)); c.commit()
        propia = taller.crear_orden(c, v1, m1, 49000, "")
        ajena = taller.crear_orden(c, v2, m2, 121000, "")
        c.close()
        self.entrar("mecanico1")
        self.assertEqual(self.cli.get("/ordenes/%d" % propia).status_code, 200)
        self.assertEqual(self.cli.get("/ordenes/%d" % ajena).status_code, 403)
        self.assertEqual(self.cli.post("/ordenes/%d/estatus" % ajena, data={"estatus": "en_proceso"}).status_code, 403)
        lista = self.cli.get("/ordenes").get_data(as_text=True)
        self.assertIn("OT-%05d" % propia, lista); self.assertNotIn("OT-%05d" % ajena, lista)

    def test_08_orden_inexistente_da_404(self):
        self.entrar("gerente.admin")
        self.assertEqual(self.cli.get("/ordenes/99999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
