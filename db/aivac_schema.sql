-- =====================================================================
-- AIVAC - Sistema Integral de Ventas y Almacén Castellanos
-- Script de creación de la base de datos (PostgreSQL)
-- Proyecto integrador - Gestión de Proyectos de Software
-- Instituto Tecnológico de Oaxaca - Equipo 1
-- =====================================================================

-- CREATE DATABASE aivac ENCODING 'UTF8';
-- \c aivac

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Seguridad y usuarios
-- ---------------------------------------------------------------------
CREATE TABLE rol (
    id_rol  SERIAL PRIMARY KEY,
    nombre  VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE usuario (
    id_usuario       SERIAL PRIMARY KEY,
    id_rol           INT          NOT NULL REFERENCES rol (id_rol),
    nombre_completo  VARCHAR(100) NOT NULL,
    nombre_usuario   VARCHAR(30)  NOT NULL UNIQUE,
    contrasena_hash  VARCHAR(255) NOT NULL,
    activo           BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ---------------------------------------------------------------------
-- 2. Clientes y vehículos
-- ---------------------------------------------------------------------
CREATE TABLE cliente (
    id_cliente             SERIAL PRIMARY KEY,
    nombre                 VARCHAR(100) NOT NULL,
    tipo_cliente           VARCHAR(15)  NOT NULL
        CHECK (tipo_cliente IN ('particular', 'flotilla', 'taller')),
    telefono               VARCHAR(15),
    correo                 VARCHAR(100),
    acepta_notificaciones  BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE vehiculo (
    id_vehiculo         SERIAL PRIMARY KEY,
    id_cliente          INT         NOT NULL REFERENCES cliente (id_cliente),
    placas              VARCHAR(10) NOT NULL UNIQUE,
    marca               VARCHAR(30),
    modelo              VARCHAR(40),
    anio                SMALLINT CHECK (anio BETWEEN 1950 AND 2100),
    tipo_uso            VARCHAR(15) NOT NULL DEFAULT 'particular'
        CHECK (tipo_uso IN ('particular', 'reparto')),
    kilometraje_actual  INT         NOT NULL DEFAULT 0 CHECK (kilometraje_actual >= 0)
);

-- ---------------------------------------------------------------------
-- 3. Catálogos de inventario y servicios
-- ---------------------------------------------------------------------
CREATE TABLE categoria (
    id_categoria  SERIAL PRIMARY KEY,
    nombre        VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE proveedor (
    id_proveedor  SERIAL PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    telefono      VARCHAR(15)
);

CREATE TABLE producto (
    id_producto   SERIAL PRIMARY KEY,
    id_categoria  INT           NOT NULL REFERENCES categoria (id_categoria),
    id_proveedor  INT           REFERENCES proveedor (id_proveedor),
    codigo        VARCHAR(20)   NOT NULL UNIQUE,
    nombre        VARCHAR(100)  NOT NULL,
    precio_compra NUMERIC(10,2) NOT NULL CHECK (precio_compra >= 0),
    precio_venta  NUMERIC(10,2) NOT NULL CHECK (precio_venta >= 0),
    stock_actual  INT           NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_minimo  INT           NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    marca          VARCHAR(50),
    descripcion    VARCHAR(300),   -- características de la refacción
    compatibilidad VARCHAR(200),   -- vehículos a los que aplica
    ubicacion      VARCHAR(30)     -- estante o anaquel dentro de la refaccionaria
);

CREATE TABLE servicio (
    id_servicio  SERIAL PRIMARY KEY,
    nombre       VARCHAR(80)   NOT NULL UNIQUE,
    precio_base  NUMERIC(10,2) NOT NULL CHECK (precio_base >= 0)
);

-- ---------------------------------------------------------------------
-- 4. Órdenes de trabajo
-- ---------------------------------------------------------------------
CREATE TABLE orden_trabajo (
    id_orden             SERIAL PRIMARY KEY,
    id_vehiculo          INT         NOT NULL REFERENCES vehiculo (id_vehiculo),
    id_mecanico          INT         NOT NULL REFERENCES usuario (id_usuario),
    fecha_ingreso        TIMESTAMP   NOT NULL DEFAULT now(),
    fecha_entrega        TIMESTAMP,
    kilometraje_ingreso  INT         NOT NULL CHECK (kilometraje_ingreso >= 0),
    estatus              VARCHAR(15) NOT NULL DEFAULT 'abierta'
        CHECK (estatus IN ('abierta', 'en_proceso', 'terminada', 'entregada', 'cancelada')),
    observaciones        TEXT,
    CHECK (fecha_entrega IS NULL OR fecha_entrega >= fecha_ingreso)
);

CREATE TABLE detalle_orden_servicio (
    id_orden         INT           NOT NULL REFERENCES orden_trabajo (id_orden) ON DELETE CASCADE,
    id_servicio      INT           NOT NULL REFERENCES servicio (id_servicio),
    precio_aplicado  NUMERIC(10,2) NOT NULL CHECK (precio_aplicado >= 0),
    PRIMARY KEY (id_orden, id_servicio)
);

CREATE TABLE solicitud_refaccion (
    id_solicitud     SERIAL PRIMARY KEY,
    id_orden         INT         NOT NULL REFERENCES orden_trabajo (id_orden),
    id_producto      INT         NOT NULL REFERENCES producto (id_producto),
    cantidad         INT         NOT NULL CHECK (cantidad > 0),
    fecha_solicitud  TIMESTAMP   NOT NULL DEFAULT now(),
    estatus          VARCHAR(15) NOT NULL DEFAULT 'pendiente'
        CHECK (estatus IN ('pendiente', 'surtida', 'sin_existencia', 'cancelada'))
);

-- ---------------------------------------------------------------------
-- 5. Ventas
-- ---------------------------------------------------------------------
CREATE TABLE venta (
    id_venta    SERIAL PRIMARY KEY,
    id_cliente  INT           REFERENCES cliente (id_cliente),
    id_usuario  INT           NOT NULL REFERENCES usuario (id_usuario),
    id_orden    INT           REFERENCES orden_trabajo (id_orden),
    fecha       TIMESTAMP     NOT NULL DEFAULT now(),
    forma_pago  VARCHAR(15)   NOT NULL
        CHECK (forma_pago IN ('efectivo', 'tarjeta', 'transferencia', 'credito')),
    monto_recibido NUMERIC(12,2) CHECK (monto_recibido >= 0),   -- solo pagos en efectivo
    cambio         NUMERIC(12,2) CHECK (cambio >= 0)
);

CREATE TABLE detalle_venta (
    id_detalle       SERIAL PRIMARY KEY,
    id_venta         INT           NOT NULL REFERENCES venta (id_venta) ON DELETE CASCADE,
    id_producto      INT           REFERENCES producto (id_producto),
    id_servicio      INT           REFERENCES servicio (id_servicio),
    cantidad         INT           NOT NULL CHECK (cantidad > 0),
    precio_unitario  NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    -- Cada partida es una refacción o un servicio, nunca ambos ni ninguno
    CHECK ((id_producto IS NOT NULL AND id_servicio IS NULL)
        OR (id_producto IS NULL AND id_servicio IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- 6. Movimientos de inventario (bitácora)
-- ---------------------------------------------------------------------
CREATE TABLE movimiento_inventario (
    id_movimiento  SERIAL PRIMARY KEY,
    id_producto    INT         NOT NULL REFERENCES producto (id_producto),
    id_usuario     INT         NOT NULL REFERENCES usuario (id_usuario),
    tipo           VARCHAR(10) NOT NULL CHECK (tipo IN ('entrada', 'salida', 'ajuste')),
    cantidad       INT         NOT NULL CHECK (cantidad <> 0),
    fecha          TIMESTAMP   NOT NULL DEFAULT now(),
    referencia     VARCHAR(50)
);

-- ---------------------------------------------------------------------
-- 7. Semáforo de desgaste y recordatorios
-- ---------------------------------------------------------------------
CREATE TABLE componente (
    id_componente    SERIAL PRIMARY KEY,
    nombre           VARCHAR(50) NOT NULL UNIQUE,
    intervalo_km     INT      NOT NULL CHECK (intervalo_km > 0),
    intervalo_dias   INT      NOT NULL CHECK (intervalo_dias > 0),
    umbral_amarillo  SMALLINT NOT NULL DEFAULT 70 CHECK (umbral_amarillo BETWEEN 1 AND 100),
    umbral_rojo      SMALLINT NOT NULL DEFAULT 90 CHECK (umbral_rojo BETWEEN 1 AND 100),
    CHECK (umbral_amarillo < umbral_rojo)
);

CREATE TABLE seguimiento_componente (
    id_seguimiento         SERIAL PRIMARY KEY,
    id_vehiculo            INT  NOT NULL REFERENCES vehiculo (id_vehiculo),
    id_componente          INT  NOT NULL REFERENCES componente (id_componente),
    km_ultimo_servicio     INT  NOT NULL CHECK (km_ultimo_servicio >= 0),
    fecha_ultimo_servicio  DATE NOT NULL,
    UNIQUE (id_vehiculo, id_componente)
);

CREATE TABLE recordatorio (
    id_recordatorio  SERIAL PRIMARY KEY,
    id_seguimiento   INT         NOT NULL REFERENCES seguimiento_componente (id_seguimiento),
    fecha_envio      TIMESTAMP,
    medio            VARCHAR(15) NOT NULL CHECK (medio IN ('whatsapp', 'sms', 'correo')),
    mensaje          TEXT        NOT NULL,
    estatus          VARCHAR(15) NOT NULL DEFAULT 'pendiente'
        CHECK (estatus IN ('pendiente', 'enviado', 'fallido'))
);

-- ---------------------------------------------------------------------
-- 8. Índices de apoyo a las consultas frecuentes
-- ---------------------------------------------------------------------
CREATE INDEX idx_vehiculo_cliente   ON vehiculo (id_cliente);
CREATE INDEX idx_orden_vehiculo     ON orden_trabajo (id_vehiculo);
CREATE INDEX idx_venta_fecha        ON venta (fecha);
CREATE INDEX idx_detalle_venta      ON detalle_venta (id_venta);
CREATE INDEX idx_mov_producto       ON movimiento_inventario (id_producto, fecha);
CREATE INDEX idx_seguimiento_veh    ON seguimiento_componente (id_vehiculo);

-- ---------------------------------------------------------------------
-- 9. Lógica de inventario sincronizado
--    Todo movimiento registrado actualiza el stock único compartido
--    entre el taller y el mostrador. Las salidas se guardan con
--    cantidad positiva y se restan; las entradas se suman; los ajustes
--    aplican su signo.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_aplicar_movimiento() RETURNS trigger AS $$
BEGIN
    IF NEW.tipo = 'entrada' THEN
        UPDATE producto SET stock_actual = stock_actual + NEW.cantidad
         WHERE id_producto = NEW.id_producto;
    ELSIF NEW.tipo = 'salida' THEN
        UPDATE producto SET stock_actual = stock_actual - NEW.cantidad
         WHERE id_producto = NEW.id_producto;
    ELSE
        UPDATE producto SET stock_actual = stock_actual + NEW.cantidad
         WHERE id_producto = NEW.id_producto;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_movimiento_stock
    AFTER INSERT ON movimiento_inventario
    FOR EACH ROW EXECUTE FUNCTION fn_aplicar_movimiento();

-- ---------------------------------------------------------------------
-- 10. Vistas: semáforo de desgaste y alertas de reabastecimiento
--     desgaste % = mayor entre (km recorridos / intervalo_km) y
--                  (días transcurridos / intervalo_dias)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_semaforo_desgaste AS
SELECT  v.id_vehiculo,
        v.placas,
        c.nombre AS componente,
        ROUND(GREATEST(
              (v.kilometraje_actual - s.km_ultimo_servicio)::numeric / c.intervalo_km,
              (CURRENT_DATE - s.fecha_ultimo_servicio)::numeric / c.intervalo_dias
        ) * 100, 1) AS desgaste_pct,
        CASE
            WHEN GREATEST(
                 (v.kilometraje_actual - s.km_ultimo_servicio)::numeric / c.intervalo_km,
                 (CURRENT_DATE - s.fecha_ultimo_servicio)::numeric / c.intervalo_dias
                 ) * 100 >= c.umbral_rojo     THEN 'rojo'
            WHEN GREATEST(
                 (v.kilometraje_actual - s.km_ultimo_servicio)::numeric / c.intervalo_km,
                 (CURRENT_DATE - s.fecha_ultimo_servicio)::numeric / c.intervalo_dias
                 ) * 100 >= c.umbral_amarillo THEN 'amarillo'
            ELSE 'verde'
        END AS estado
FROM    seguimiento_componente s
JOIN    vehiculo   v ON v.id_vehiculo   = s.id_vehiculo
JOIN    componente c ON c.id_componente = s.id_componente;

-- El subtotal y el total no se almacenan (dependencias transitivas, 3FN);
-- se calculan en estas vistas a partir de cantidad y precio_unitario.
CREATE OR REPLACE VIEW v_detalle_venta AS
SELECT  id_detalle, id_venta, id_producto, id_servicio, cantidad, precio_unitario,
        cantidad * precio_unitario AS subtotal
FROM    detalle_venta;

CREATE OR REPLACE VIEW v_venta_total AS
SELECT  v.id_venta, v.fecha, v.forma_pago, v.id_cliente, v.id_usuario,
        COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
FROM    venta v
LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
GROUP BY v.id_venta, v.fecha, v.forma_pago, v.id_cliente, v.id_usuario;

CREATE OR REPLACE VIEW v_alerta_reabasto AS
SELECT  id_producto, codigo, nombre, stock_actual, stock_minimo
FROM    producto
WHERE   stock_actual <= stock_minimo;

-- ---------------------------------------------------------------------
-- 11. Datos iniciales (catálogos). Los intervalos de los componentes son
--     valores de partida parametrizables, por validar con los mecánicos.
-- ---------------------------------------------------------------------
INSERT INTO rol (nombre) VALUES
    ('Gerente Principal'), ('Gerente Administrativa'),
    ('Jefe de Refaccionaria'), ('Mecánico'), ('Repartidor');

INSERT INTO componente (nombre, intervalo_km, intervalo_dias, umbral_amarillo, umbral_rojo) VALUES
    ('Aceite de motor',   5000,  180, 70, 90),
    ('Balatas',          30000,  730, 70, 90),
    ('Bujías',           40000,  730, 70, 90),
    ('Bandas',           60000, 1460, 70, 90),
    ('Amortiguadores',   60000, 1460, 70, 90),
    ('Neumáticos',       40000, 1460, 70, 90);

INSERT INTO categoria (nombre) VALUES
    ('Frenos'), ('Lubricantes'), ('Encendido'), ('Suspensión'), ('Llantas'), ('Bandas y mangueras');

INSERT INTO servicio (nombre, precio_base) VALUES
    ('Alineación', 350.00), ('Balanceo computarizado', 250.00),
    ('Cambio de aceite', 200.00), ('Afinación general', 800.00),
    ('Revisión de suspensión', 300.00), ('Cambio de balatas', 450.00);

COMMIT;
