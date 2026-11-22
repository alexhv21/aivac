-- Pruebas de la base de datos AIVAC (Iteración 1). Ejecutar con:
--   psql -d aivac_bd -f aivac_schema.sql ; psql -d aivac_bd -f pruebas_bd.sql
-- Cada prueba imprime PASS o FAIL. Todo se revierte al final (ROLLBACK).
\set ON_ERROR_STOP off
BEGIN;
-- Datos de apoyo
INSERT INTO usuario (id_rol, nombre_completo, nombre_usuario, contrasena_hash) VALUES (1, 'Usuario de prueba', 'u_prueba', 'hash');
INSERT INTO cliente (nombre, tipo_cliente) VALUES ('Cliente de prueba', 'particular');
INSERT INTO vehiculo (id_cliente, placas, marca, modelo, anio, kilometraje_actual) VALUES (1, 'PRB-001', 'Nissan', 'Versa', 2018, 48000);
INSERT INTO producto (id_categoria, codigo, nombre, precio_compra, precio_venta, stock_actual, stock_minimo) VALUES (1, 'P-1', 'Producto 1', 100, 150, 10, 3);
INSERT INTO servicio (nombre, precio_base) VALUES ('Servicio de prueba', 200);

-- BD-01 Placas únicas
DO $$ BEGIN
  BEGIN INSERT INTO vehiculo (id_cliente, placas) VALUES (1, 'PRB-001'); RAISE NOTICE 'FAIL BD-01 placas duplicadas aceptadas';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'PASS BD-01 Se rechazan placas duplicadas (UNIQUE)'; END; END $$;
-- BD-02 Stock no negativo
DO $$ BEGIN
  BEGIN UPDATE producto SET stock_actual = -1 WHERE codigo = 'P-1'; RAISE NOTICE 'FAIL BD-02 stock negativo aceptado';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS BD-02 Se rechaza un stock negativo (CHECK)'; END; END $$;
-- BD-03 Partida con producto y servicio a la vez
DO $$ BEGIN
  INSERT INTO venta (id_usuario, forma_pago) VALUES (1, 'efectivo');
  BEGIN INSERT INTO detalle_venta (id_venta, id_producto, id_servicio, cantidad, precio_unitario) VALUES (1, 1, 1, 1, 10); RAISE NOTICE 'FAIL BD-03 partida mixta aceptada';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS BD-03 Se rechaza una partida con producto y servicio simultáneos (CHECK)'; END; END $$;
-- BD-04 Partida sin producto ni servicio
DO $$ BEGIN
  BEGIN INSERT INTO detalle_venta (id_venta, cantidad, precio_unitario) VALUES (1, 1, 10); RAISE NOTICE 'FAIL BD-04 partida vacía aceptada';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS BD-04 Se rechaza una partida sin producto ni servicio (CHECK)'; END; END $$;
-- BD-05 Forma de pago inválida
DO $$ BEGIN
  BEGIN INSERT INTO venta (id_usuario, forma_pago) VALUES (1, 'cheque'); RAISE NOTICE 'FAIL BD-05 forma de pago inválida aceptada';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS BD-05 Se rechaza una forma de pago no permitida (CHECK)'; END; END $$;
-- BD-06 Integridad referencial
DO $$ BEGIN
  BEGIN INSERT INTO vehiculo (id_cliente, placas) VALUES (9999, 'XXX-999'); RAISE NOTICE 'FAIL BD-06 vehículo de cliente inexistente aceptado';
  EXCEPTION WHEN foreign_key_violation THEN RAISE NOTICE 'PASS BD-06 Se rechaza un vehículo de un cliente inexistente (FK)'; END; END $$;
-- BD-07 Cantidad cero
DO $$ BEGIN
  BEGIN INSERT INTO detalle_venta (id_venta, id_servicio, cantidad, precio_unitario) VALUES (1, 1, 0, 10); RAISE NOTICE 'FAIL BD-07 cantidad cero aceptada';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS BD-07 Se rechaza una cantidad igual a cero (CHECK)'; END; END $$;
-- BD-08 Disparador: salida descuenta
DO $$ DECLARE s int; BEGIN
  INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad) VALUES (1, 1, 'salida', 4);
  SELECT stock_actual INTO s FROM producto WHERE id_producto = 1;
  IF s = 6 THEN RAISE NOTICE 'PASS BD-08 Una salida de 4 baja el stock de 10 a 6 (disparador)'; ELSE RAISE NOTICE 'FAIL BD-08 stock=%', s; END IF; END $$;
-- BD-09 Disparador: entrada suma
DO $$ DECLARE s int; BEGIN
  INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad) VALUES (1, 1, 'entrada', 5);
  SELECT stock_actual INTO s FROM producto WHERE id_producto = 1;
  IF s = 11 THEN RAISE NOTICE 'PASS BD-09 Una entrada de 5 sube el stock de 6 a 11 (disparador)'; ELSE RAISE NOTICE 'FAIL BD-09 stock=%', s; END IF; END $$;
-- BD-10 Disparador: ajuste negativo
DO $$ DECLARE s int; BEGIN
  INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad) VALUES (1, 1, 'ajuste', -2);
  SELECT stock_actual INTO s FROM producto WHERE id_producto = 1;
  IF s = 9 THEN RAISE NOTICE 'PASS BD-10 Un ajuste de -2 baja el stock de 11 a 9 (disparador)'; ELSE RAISE NOTICE 'FAIL BD-10 stock=%', s; END IF; END $$;
-- BD-11 Salida mayor a la existencia
DO $$ BEGIN
  BEGIN INSERT INTO movimiento_inventario (id_producto, id_usuario, tipo, cantidad) VALUES (1, 1, 'salida', 500); RAISE NOTICE 'FAIL BD-11 salida mayor a la existencia aceptada';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS BD-11 Una salida mayor a la existencia se rechaza y no deja stock negativo'; END; END $$;
-- BD-12 Total de venta
DO $$ DECLARE t numeric; BEGIN
  INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario) VALUES (1, 1, 2, 150);
  INSERT INTO detalle_venta (id_venta, id_servicio, cantidad, precio_unitario) VALUES (1, 1, 1, 200);
  SELECT total INTO t FROM v_venta_total WHERE id_venta = 1;
  IF t = 500 THEN RAISE NOTICE 'PASS BD-12 v_venta_total calcula 2 x 150 + 1 x 200 = 500.00'; ELSE RAISE NOTICE 'FAIL BD-12 total=%', t; END IF; END $$;
-- BD-13 Alerta de reabasto
DO $$ DECLARE n int; BEGIN
  UPDATE producto SET stock_actual = 3 WHERE id_producto = 1;
  SELECT count(*) INTO n FROM v_alerta_reabasto WHERE codigo = 'P-1';
  IF n = 1 THEN RAISE NOTICE 'PASS BD-13 v_alerta_reabasto lista el producto con stock igual al mínimo'; ELSE RAISE NOTICE 'FAIL BD-13'; END IF; END $$;
-- BD-14/15/16 Semáforo de desgaste (aceite: 5000 km / 180 días; umbrales 70 y 90)
DO $$ DECLARE e text; p numeric; BEGIN
  INSERT INTO seguimiento_componente (id_vehiculo, id_componente, km_ultimo_servicio, fecha_ultimo_servicio) VALUES (1, 1, 46000, CURRENT_DATE - 10);
  SELECT estado, desgaste_pct INTO e, p FROM v_semaforo_desgaste WHERE placas = 'PRB-001' AND componente = 'Aceite de motor';
  IF e = 'verde' THEN RAISE NOTICE 'PASS BD-14 2,000 km de 5,000 (%) y 10 días: semáforo verde', p; ELSE RAISE NOTICE 'FAIL BD-14 estado=%', e; END IF;
  UPDATE seguimiento_componente SET km_ultimo_servicio = 44000;
  SELECT estado, desgaste_pct INTO e, p FROM v_semaforo_desgaste WHERE placas = 'PRB-001' AND componente = 'Aceite de motor';
  IF e = 'amarillo' THEN RAISE NOTICE 'PASS BD-15 4,000 km de 5,000 (%): semáforo amarillo', p; ELSE RAISE NOTICE 'FAIL BD-15 estado=%', e; END IF;
  UPDATE seguimiento_componente SET km_ultimo_servicio = 43000;
  SELECT estado, desgaste_pct INTO e, p FROM v_semaforo_desgaste WHERE placas = 'PRB-001' AND componente = 'Aceite de motor';
  IF e = 'rojo' THEN RAISE NOTICE 'PASS BD-16 5,000 km de 5,000 (%): semáforo rojo', p; ELSE RAISE NOTICE 'FAIL BD-16 estado=%', e; END IF; END $$;
-- BD-17 El criterio de tiempo también cuenta (km bajos pero 200 días)
DO $$ DECLARE e text; BEGIN
  UPDATE seguimiento_componente SET km_ultimo_servicio = 47900, fecha_ultimo_servicio = CURRENT_DATE - 200;
  SELECT estado INTO e FROM v_semaforo_desgaste WHERE placas = 'PRB-001' AND componente = 'Aceite de motor';
  IF e = 'rojo' THEN RAISE NOTICE 'PASS BD-17 Con solo 100 km pero 200 días (> 180) el semáforo es rojo (se usa el mayor de ambos criterios)'; ELSE RAISE NOTICE 'FAIL BD-17 estado=%', e; END IF; END $$;
-- BD-18 Umbrales incoherentes
DO $$ BEGIN
  BEGIN INSERT INTO componente (nombre, intervalo_km, intervalo_dias, umbral_amarillo, umbral_rojo) VALUES ('X', 1000, 100, 90, 70); RAISE NOTICE 'FAIL BD-18 umbrales incoherentes aceptados';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS BD-18 Se rechaza umbral amarillo mayor que el rojo (CHECK)'; END; END $$;
ROLLBACK;
