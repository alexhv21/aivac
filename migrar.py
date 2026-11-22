"""Actualiza una base de datos creada con una versión anterior del esquema. Es seguro ejecutarlo varias veces.

Agrega: ficha de refacciones (marca, características, compatibilidad, ubicación) y, en ventas, el efectivo
recibido y el cambio entregado. Se ejecuta automáticamente desde iniciar.bat y cargar_datos.bat.
"""
import db
import fichas

CAMBIOS = [
    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS marca VARCHAR(50)",
    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS descripcion VARCHAR(300)",
    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS compatibilidad VARCHAR(200)",
    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS ubicacion VARCHAR(30)",
    "ALTER TABLE venta ADD COLUMN IF NOT EXISTS monto_recibido NUMERIC(12,2) CHECK (monto_recibido >= 0)",
    "ALTER TABLE venta ADD COLUMN IF NOT EXISTS cambio NUMERIC(12,2) CHECK (cambio >= 0)",
]


def aplicar(conn):
    cur = conn.cursor()
    for sql in CAMBIOS:
        cur.execute(sql)
    conn.commit()
    fichas.completar(conn)


if __name__ == "__main__":
    c = db.conectar()
    aplicar(c)
    c.close()
    print("Base de datos al día.")
