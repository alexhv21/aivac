"""Aplicación web AIVAC — módulo de ventas (Sprint 2).

Ejecución en desarrollo:
    export AIVAC_DSN="dbname=aivac user=aivac host=localhost"
    export AIVAC_SECRET="cambiar-en-produccion"
    flask --app app run
"""
import os
from datetime import datetime

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for

import auth
import db
import catalogo
import taller
import ventas


def crear_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("AIVAC_SECRET", "solo-desarrollo")

    # --- una conexión (y transacción) por petición -------------------------------------
    def conexion():
        if "conn" not in g:
            g.conn = db.conectar()
        return g.conn

    @app.teardown_appcontext
    def cerrar(_exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.rollback()  # lo no confirmado se descarta
            conn.close()

    @app.template_filter("fh")
    def formato_fecha(valor):
        """Muestra fecha y hora como dd/mm/aaaa hh:mm (acepta datetime o texto ISO)."""
        if isinstance(valor, str):
            valor = datetime.fromisoformat(valor)
        return valor.strftime("%d/%m/%Y %H:%M")

    @app.context_processor
    def datos_de_plantilla():
        return {"usuario": session.get("nombre"), "rol": session.get("rol"),
                "puede_vender": session.get("rol") in auth.ROLES_VENTAS,
                "puede_ver_inventario": session.get("rol") in auth.ROLES_INVENTARIO,
                "puede_refacciones": session.get("rol") in auth.ROLES_INVENTARIO,
                "puede_clientes": session.get("rol") in auth.ROLES_CLIENTES,
                "puede_ordenes": session.get("rol") in auth.ROLES_ORDENES,
                "etiqueta_estatus": taller.ETIQUETA_ESTATUS}

    # --- acceso ----------------------------------------------------------------------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            cur = conexion().cursor()
            u = auth.autenticar(cur, request.form.get("usuario", "").strip(), request.form.get("contrasena", ""))
            if u:
                session.clear()
                session.update(id_usuario=u["id_usuario"], nombre=u["nombre_completo"], rol=u["rol"])
                return redirect(url_for("inicio"))
            error = "Usuario o contraseña incorrectos."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    def inicio():
        if "id_usuario" not in session:
            return redirect(url_for("login"))
        if session["rol"] in auth.ROLES_VENTAS:
            return redirect(url_for("nueva_venta"))
        if session["rol"] in auth.ROLES_ORDENES:
            return redirect(url_for("lista_ordenes"))
        if session["rol"] in auth.ROLES_INVENTARIO:
            return redirect(url_for("ver_inventario"))
        return render_template("sin_modulos.html")

    # --- ventas ----------------------------------------------------------------------
    @app.route("/ventas/nueva")
    @auth.rol_requerido(*auth.ROLES_VENTAS)
    def nueva_venta():
        return render_template("nueva_venta.html", formas_pago=ventas.FORMAS_PAGO)

    @app.route("/api/catalogo")
    @auth.rol_requerido(*auth.ROLES_VENTAS)
    def api_catalogo():
        texto = request.args.get("q", "")
        if len(texto.strip()) < 2:
            return jsonify([])
        filas = ventas.buscar_catalogo(conexion().cursor(), texto)
        return jsonify([{**f, "precio": float(f["precio"])} for f in filas])

    @app.route("/api/clientes")
    @auth.rol_requerido(*auth.ROLES_VENTAS)
    def api_clientes():
        texto = request.args.get("q", "")
        if len(texto.strip()) < 2:
            return jsonify([])
        return jsonify(ventas.buscar_clientes(conexion().cursor(), texto))

    @app.route("/ventas", methods=["POST"])
    @auth.rol_requerido(*auth.ROLES_VENTAS)
    def registrar_venta():
        datos = request.get_json(silent=True) or {}
        try:
            if datos.get("forma_pago") == "efectivo" and datos.get("monto_recibido") in (None, ""):
                raise ventas.VentaError("Indique cuánto efectivo recibió del cliente para calcular el cambio.")
            id_venta = ventas.registrar_venta(conexion(), session["id_usuario"], datos.get("id_cliente") or None,
                                              datos.get("forma_pago"), datos.get("partidas"), datos.get("monto_recibido"))
        except ventas.VentaError as e:
            return jsonify({"ok": False, "error": str(e)}), 422
        return jsonify({"ok": True, "id_venta": id_venta, "url": url_for("ver_comprobante", id_venta=id_venta)})

    @app.route("/ventas/<int:id_venta>/comprobante")
    @auth.rol_requerido(*auth.ROLES_VENTAS)
    def ver_comprobante(id_venta):
        cab, partidas, total = ventas.comprobante(conexion().cursor(), id_venta)
        if cab is None:
            abort(404)
        return render_template("comprobante.html", cab=cab, partidas=partidas, total=total)

    @app.route("/ventas")
    @auth.rol_requerido(*auth.ROLES_VENTAS)
    def lista_ventas():
        return render_template("ventas.html", filas=ventas.ventas_recientes(conexion().cursor()))

    # --- inventario (consulta) ---------------------------------------------------------
    @app.route("/inventario")
    @auth.rol_requerido(*auth.ROLES_INVENTARIO)
    def ver_inventario():
        return render_template("inventario.html", filas=ventas.inventario(conexion().cursor()))

    # --- catálogo de refacciones --------------------------------------------------------------
    @app.route("/refacciones")
    @auth.rol_requerido(*auth.ROLES_INVENTARIO)
    def lista_refacciones():
        q = request.args.get("q", "")
        cat = request.args.get("categoria", "")
        cur = conexion().cursor()
        return render_template("refacciones.html", filas=catalogo.listar(cur, q, int(cat) if cat.isdigit() else None),
                               q=q, cat=cat, categorias=catalogo.categorias(cur))

    @app.route("/refacciones/nueva", methods=["GET", "POST"])
    @app.route("/refacciones/<int:id_producto>/editar", methods=["GET", "POST"])
    @auth.rol_requerido(*auth.ROLES_INVENTARIO)
    def form_refaccion(id_producto=None):
        cur = conexion().cursor()
        datos, error = {}, None
        if id_producto is not None:
            datos = catalogo.obtener(cur, id_producto) or abort(404)
        if request.method == "POST":
            datos = request.form.to_dict()
            try:
                id_producto = catalogo.guardar(conexion(), session["id_usuario"], datos, id_producto)
                flash("Refacción guardada.")
                return redirect(url_for("ver_refaccion", id_producto=id_producto))
            except catalogo.CatalogoError as e:
                error = str(e)
        cur = conexion().cursor()
        return render_template("form_refaccion.html", d=datos, error=error, nuevo=id_producto is None,
                               categorias=catalogo.categorias(cur), proveedores=catalogo.proveedores(cur))

    @app.route("/refacciones/<int:id_producto>")
    @auth.rol_requerido(*auth.ROLES_INVENTARIO)
    def ver_refaccion(id_producto):
        cur = conexion().cursor()
        p = catalogo.obtener(cur, id_producto) or abort(404)
        return render_template("refaccion.html", p=p, movs=catalogo.movimientos(cur, id_producto))

    @app.route("/refacciones/<int:id_producto>/entrada", methods=["POST"])
    @auth.rol_requerido(*auth.ROLES_INVENTARIO)
    def entrada_refaccion(id_producto):
        try:
            catalogo.registrar_entrada(conexion(), session["id_usuario"], id_producto, request.form.get("cantidad"), request.form.get("motivo"))
            flash("Entrada registrada: la existencia se actualizó.")
        except catalogo.CatalogoError as e:
            flash(str(e), "err")
        return redirect(url_for("ver_refaccion", id_producto=id_producto))

    # --- clientes y vehículos -------------------------------------------------------------
    @app.route("/clientes")
    @auth.rol_requerido(*auth.ROLES_CLIENTES)
    def lista_clientes():
        q = request.args.get("q", "")
        return render_template("clientes.html", filas=taller.listar_clientes(conexion().cursor(), q), q=q)

    @app.route("/clientes/nuevo", methods=["GET", "POST"])
    @app.route("/clientes/<int:id_cliente>/editar", methods=["GET", "POST"])
    @auth.rol_requerido(*auth.ROLES_CLIENTES)
    def form_cliente(id_cliente=None):
        datos, error = {}, None
        if id_cliente is not None:
            datos = taller.obtener_cliente(conexion().cursor(), id_cliente) or abort(404)
        if request.method == "POST":
            datos = {**request.form.to_dict(), "acepta_notificaciones": "acepta_notificaciones" in request.form}
            try:
                id_cliente = taller.guardar_cliente(conexion(), datos, id_cliente)
                flash("Cliente guardado.")
                return redirect(url_for("ficha_cliente", id_cliente=id_cliente))
            except taller.TallerError as e:
                error = str(e)
        return render_template("form_cliente.html", d=datos, error=error, tipos=taller.TIPOS_CLIENTE, nuevo=id_cliente is None)

    @app.route("/clientes/<int:id_cliente>")
    @auth.rol_requerido(*auth.ROLES_CLIENTES)
    def ficha_cliente(id_cliente):
        cur = conexion().cursor()
        cli = taller.obtener_cliente(cur, id_cliente) or abort(404)
        return render_template("ficha_cliente.html", c=cli, vehiculos=taller.listar_vehiculos(cur, id_cliente=id_cliente))

    @app.route("/vehiculos")
    @auth.rol_requerido(*auth.ROLES_CLIENTES)
    def lista_vehiculos():
        q = request.args.get("q", "")
        return render_template("vehiculos.html", filas=taller.listar_vehiculos(conexion().cursor(), q), q=q)

    @app.route("/vehiculos/nuevo", methods=["GET", "POST"])
    @app.route("/vehiculos/<int:id_vehiculo>/editar", methods=["GET", "POST"])
    @auth.rol_requerido(*auth.ROLES_CLIENTES)
    def form_vehiculo(id_vehiculo=None):
        cur = conexion().cursor()
        datos, error = {"id_cliente": request.args.get("cliente", "")}, None
        if id_vehiculo is not None:
            datos = taller.obtener_vehiculo(cur, id_vehiculo) or abort(404)
        if request.method == "POST":
            datos = request.form.to_dict()
            try:
                id_vehiculo = taller.guardar_vehiculo(conexion(), datos, id_vehiculo)
                flash("Vehículo guardado.")
                return redirect(url_for("ficha_cliente", id_cliente=int(datos["id_cliente"])))
            except taller.TallerError as e:
                error = str(e)
        cur = conexion().cursor()
        return render_template("form_vehiculo.html", d=datos, error=error, usos=taller.TIPOS_USO,
                               clientes=taller.listar_clientes(cur), nuevo=id_vehiculo is None)

    # --- órdenes de trabajo -----------------------------------------------------------------
    def _solo_propias():
        """Id del mecánico cuyas órdenes se pueden ver (None = todas, para los demás roles)."""
        return session["id_usuario"] if session.get("rol") == "Mecánico" else None

    def _orden_visible(id_orden):
        cab, servicios, refacciones, total = taller.obtener_orden(conexion().cursor(), id_orden)
        if cab is None:
            abort(404)
        if _solo_propias() and cab["id_mecanico"] != session["id_usuario"]:
            abort(403)
        return cab, servicios, refacciones, total

    @app.route("/ordenes")
    @auth.rol_requerido(*auth.ROLES_ORDENES)
    def lista_ordenes():
        est = request.args.get("estatus") or None
        if est not in taller.ESTATUS_ORDEN:
            est = None
        return render_template("ordenes.html", filas=taller.listar_ordenes(conexion().cursor(), est, _solo_propias()),
                               estatus=est, estatuses=taller.ESTATUS_ORDEN)

    @app.route("/ordenes/nueva", methods=["GET", "POST"])
    @auth.rol_requerido(*auth.ROLES_ORDENES)
    def nueva_orden():
        cur = conexion().cursor()
        datos, error = {"id_vehiculo": request.args.get("vehiculo", "")}, None
        if request.method == "POST":
            datos = request.form.to_dict()
            mec = session["id_usuario"] if session["rol"] == "Mecánico" else datos.get("id_mecanico")
            try:
                id_orden = taller.crear_orden(conexion(), datos.get("id_vehiculo"), mec, datos.get("kilometraje"), datos.get("observaciones"))
                flash("Orden de trabajo abierta.")
                return redirect(url_for("ver_orden", id_orden=id_orden))
            except taller.TallerError as e:
                error = str(e)
        cur = conexion().cursor()
        km = ""
        if str(datos.get("id_vehiculo", "")).isdigit():
            v = taller.obtener_vehiculo(cur, int(datos["id_vehiculo"]))
            km = v["kilometraje_actual"] if v else ""
        return render_template("nueva_orden.html", d=datos, error=error, km=datos.get("kilometraje") or km,
                               vehiculos=taller.listar_vehiculos(cur), mecanicos=taller.mecanicos(cur))

    @app.route("/ordenes/<int:id_orden>")
    @auth.rol_requerido(*auth.ROLES_ORDENES)
    def ver_orden(id_orden):
        cab, servicios, refacciones, total = _orden_visible(id_orden)
        cur = conexion().cursor()
        return render_template("orden.html", o=cab, servicios=servicios, refacciones=refacciones, total=total,
                               cat_servicios=taller.servicios_catalogo(cur), cat_productos=taller.productos_catalogo(cur),
                               siguientes=taller.TRANSICIONES[cab["estatus"]], editable=cab["estatus"] in taller.EDITABLES)

    def _accion_orden(id_orden, funcion):
        _orden_visible(id_orden)
        try:
            msg = funcion()
            flash(msg or "Cambio guardado.")
        except taller.TallerError as e:
            flash(str(e), "err")
        return redirect(url_for("ver_orden", id_orden=id_orden))

    @app.route("/ordenes/<int:id_orden>/servicio", methods=["POST"])
    @auth.rol_requerido(*auth.ROLES_ORDENES)
    def orden_servicio(id_orden):
        return _accion_orden(id_orden, lambda: taller.agregar_servicio(conexion(), id_orden, request.form.get("id_servicio")) or "Servicio agregado.")

    @app.route("/ordenes/<int:id_orden>/refaccion", methods=["POST"])
    @auth.rol_requerido(*auth.ROLES_ORDENES)
    def orden_refaccion(id_orden):
        def hacer():
            est = taller.solicitar_refaccion(conexion(), session["id_usuario"], id_orden, request.form.get("id_producto"), request.form.get("cantidad"))
            return "Refacción surtida y descontada del inventario." if est == "surtida" else "No hay existencia suficiente: la solicitud quedó registrada como «sin existencia»."
        return _accion_orden(id_orden, hacer)

    @app.route("/ordenes/<int:id_orden>/estatus", methods=["POST"])
    @auth.rol_requerido(*auth.ROLES_ORDENES)
    def orden_estatus(id_orden):
        def hacer():
            taller.cambiar_estatus(conexion(), session["id_usuario"], id_orden, request.form.get("estatus"))
            return "Estatus actualizado."
        return _accion_orden(id_orden, hacer)

    @app.errorhandler(403)
    def prohibido(_e):
        return render_template("403.html"), 403

    return app


app = crear_app()
