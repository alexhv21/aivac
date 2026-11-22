"""Pruebas de integración de la aplicación web (rutas, sesión y permisos por rol)."""
import unittest

import soporte
from app import crear_app

CLAVE = "Demo2026!"


def setUpModule():
    soporte.guardar_stock_inicial()


class PruebasApp(unittest.TestCase):
    def setUp(self):
        soporte.restaurar()
        self.cli = crear_app().test_client()
        c = soporte.conn(); self.stock_inicial = soporte.stock(c.cursor(), "BAL-001"); c.close()

    def entrar(self, usuario, clave=CLAVE):
        return self.cli.post("/login", data={"usuario": usuario, "contrasena": clave})

    def test_01_login_valido_redirige_a_nueva_venta(self):
        r = self.entrar("gerente.admin")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.cli.get("/", follow_redirects=False).headers["Location"], "/ventas/nueva")

    def test_02_login_con_clave_incorrecta(self):
        r = self.entrar("gerente.admin", "otra")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Usuario o contraseña incorrectos", r.get_data(as_text=True))

    def test_03_usuario_inactivo_no_entra(self):
        c = soporte.conn(); c.cursor().execute("UPDATE usuario SET activo = FALSE WHERE nombre_usuario = 'gerente.admin'"); c.commit(); c.close()
        self.assertIn("incorrectos", self.entrar("gerente.admin").get_data(as_text=True))

    def test_04_sin_sesion_redirige_a_login(self):
        r = self.cli.get("/ventas/nueva")
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/login"))

    def test_05_mecanico_no_puede_vender(self):
        self.entrar("mecanico1")
        self.assertEqual(self.cli.get("/ventas/nueva").status_code, 403)
        self.assertEqual(self.cli.post("/ventas", json={"forma_pago": "efectivo", "partidas": []}).status_code, 403)

    def test_06_jefe_de_refaccionaria_si_puede_vender(self):
        self.entrar("refacciones")
        self.assertEqual(self.cli.get("/ventas/nueva").status_code, 200)

    def test_07_post_venta_correcta_y_comprobante(self):
        self.entrar("gerente.admin")
        r = self.cli.post("/ventas", json={"id_cliente": 1, "forma_pago": "tarjeta", "partidas": [{"tipo": "producto", "id": 1, "cantidad": 2}]})
        self.assertEqual(r.status_code, 200)
        pag = self.cli.get(r.json["url"]).get_data(as_text=True)
        self.assertIn("$1,040.00", pag)
        self.assertIn("Juan Pérez Demo", pag)

    def test_08_post_sin_forma_de_pago_devuelve_422_y_no_cambia_stock(self):
        self.entrar("gerente.admin")
        c = soporte.conn(); cur = c.cursor()
        antes = soporte.stock(cur, "BAL-001")
        r = self.cli.post("/ventas", json={"partidas": [{"tipo": "producto", "id": 1, "cantidad": 1}]})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(soporte.stock(cur, "BAL-001"), antes); c.close()

    def test_09_comprobante_inexistente_404(self):
        self.entrar("gerente.admin")
        self.assertEqual(self.cli.get("/ventas/9999/comprobante").status_code, 404)

    def test_10_inventario_refleja_la_venta(self):
        self.entrar("refacciones")
        self.cli.post("/ventas", json={"forma_pago": "efectivo", "partidas": [{"tipo": "producto", "id": 1, "cantidad": 3}]})
        html = self.cli.get("/inventario").get_data(as_text=True)
        self.assertIn("<b>%d</b>" % (self.stock_inicial - 3), html)

    def test_11_la_contrasena_no_se_guarda_en_texto_plano(self):
        c = soporte.conn(); cur = c.cursor()
        cur.execute("SELECT count(*) AS n FROM usuario WHERE contrasena_hash = %s", (CLAVE,))
        self.assertEqual(cur.fetchone()["n"], 0); c.close()

    def test_12_busqueda_api_exige_al_menos_dos_letras(self):
        self.entrar("gerente.admin")
        self.assertEqual(self.cli.get("/api/catalogo?q=a").json, [])
        self.assertGreater(len(self.cli.get("/api/catalogo?q=ace").json), 0)

    def test_13_precio_enviado_por_el_cliente_se_ignora(self):
        self.entrar("gerente.admin")
        r = self.cli.post("/ventas", json={"forma_pago": "efectivo", "monto_recibido": 600, "partidas": [{"tipo": "producto", "id": 1, "cantidad": 1, "precio": 1}]})
        self.assertIn("$520.00", self.cli.get(r.json["url"]).get_data(as_text=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
