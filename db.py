"""Acceso a la base de datos PostgreSQL de AIVAC.

La cadena de conexión se toma de la variable de entorno AIVAC_DSN, por ejemplo:
    AIVAC_DSN="dbname=aivac user=aivac password=*** host=localhost"
Cada petición HTTP usa una conexión propia (con transacción) que se confirma o se
revierte al terminar, de modo que una venta nunca queda a medias.
"""
import os

import psycopg2
from psycopg2.extras import RealDictCursor


def conectar():
    """Abre una conexión nueva cuyos cursores devuelven filas como diccionarios."""
    dsn = os.environ.get("AIVAC_DSN", "dbname=aivac user=aivac host=localhost")
    return psycopg2.connect(dsn, cursor_factory=RealDictCursor)
