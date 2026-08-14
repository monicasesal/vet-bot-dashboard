# Rutas de la página web (bento grid) // Blueprint = Router

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from urllib.parse import unquote
from database.conexion import db, obtener_conversaciones, cambiar_estado_chat, eliminar_cita_db, actualizar_cita_db
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from utils.citas_utils import calcular_hora_fin, verificar_disponibilidad

web_blueprint = Blueprint('web', __name__)


@web_blueprint.route('/')
def inicio():
    #muestra la pag principal cargando todas las citas y chats desde MongoDB
    citas_desde_mongo = list(db.citas.find())

    # Fechas de referencia
    hoy = datetime.now()
    fecha_hoy_str = hoy.strftime('%Y-%m-%d')

    # Inicio de semana (Lunes) e inicio de mes (Día 1)
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana_str = inicio_semana.strftime('%Y-%m-%d')
    inicio_mes_str = hoy.strftime('%Y-%m-01')

    # Asegurar 'hora_fin' en todas las citas
    for cita in citas_desde_mongo:
        if 'hora' in cita and not cita.get('hora_fin'):
            duracion = cita.get('duracion_minutos', 30)
            cita['hora_fin'] = calcular_hora_fin(cita['hora'], duracion)

    # Filtrar solo las citas de hoy para la tarjeta principal
    citas_hoy = [c for c in citas_desde_mongo if c.get('fecha') == fecha_hoy_str or not c.get('fecha')]

    # Cálculos dinámicos
    citas_dia = 0
    citas_semana = 0
    citas_mes = 0

    for cita in citas_desde_mongo:
        fecha_cita = cita.get('fecha')

        # Si la cita tiene fecha guardada
        if fecha_cita:
            if fecha_cita == fecha_hoy_str:
                citas_dia += 1
            if fecha_cita >= inicio_semana_str:
                citas_semana += 1
            if fecha_cita >= inicio_mes_str:
                citas_mes += 1
        else:
            # Para citas antiguas que no tengan campo 'fecha', contabilizar en el día por defecto
            citas_dia += 1
            citas_semana += 1
            citas_mes += 1

    stats_citas = {
        'dia': citas_dia,
        'semana': citas_semana,
        'mes': citas_mes
    }

    # NUEVO: conversaciones que requieren atención humana (sustituye a la antigua
    # tarjeta "Chats en Tiempo Real", que además usaba campos que no existían en el
    # esquema real: chat.usuario y comparaba atendido_por == "Humano" con mayúscula,
    # cuando el valor real guardado es "humano" en minúscula - por eso nunca marcaba
    # nada como urgente aunque el campo estuviera bien puesto).
    conversaciones_todas = obtener_conversaciones()
    chats_atencion_humana = [c for c in conversaciones_todas if c.get('atendido_por') == 'humano']

    return render_template(
        'index.html',
        mis_citas_hoy=citas_hoy,
        stats=stats_citas,
        fecha_hoy=fecha_hoy_str,
        chats_atencion_humana=chats_atencion_humana
    )


@web_blueprint.route('/nueva-cita', methods=['POST'])
def nueva_cita():
    #recibe los datos del form, crea una nueva cita CON VALIDACIÓN DE SOLAPAMIENTO, la guarda en MongoDB y redirige a la pag principal
    hora_form = request.form.get('hora')
    fecha_form = request.form.get('fecha')
    paciente_form = request.form.get('paciente')
    motivo_form = request.form.get('motivo')
    duracion_form = int(request.form.get('duracion', 30)) #la duración del form o 30min por defecto

    if not fecha_form:
        fecha_form = datetime.now().strftime('%Y-%m-%d')

    #verificar si hay solapamiento en Mongodb (reemplaza la consulta exacta antigua)
    disponible, mensaje = verificar_disponibilidad(db, fecha_form, hora_form, duracion_form)

    if not disponible:
        flash(f'⚠️ {mensaje}', 'warning')
        return redirect('/')

    hora_fin_form = calcular_hora_fin(hora_form, duracion_form)


    #guardar la cita
    cita_nueva = {
        "fecha": fecha_form,
        "hora": hora_form,
        "duracion_minutos": duracion_form,
        "hora_fin": hora_fin_form,
        "paciente": paciente_form,
        "motivo": motivo_form
    }

    #insertar en la colección correspondiente
    db.citas.insert_one(cita_nueva)
    flash('✅ Cita agendada con éxito.', 'success')
    return redirect('/')


@web_blueprint.route('/chat')
def chat_admin():
    telefono_raw = request.args.get('telefono')

    telefono_seleccionado = unquote(telefono_raw) if telefono_raw else None

    #si hay un chat seleccionado, marcamos sus mensajes como LEÍDOS
    if telefono_seleccionado:
        db.chats.update_many(
            {"telefono": telefono_seleccionado, "rol": "user", "leido": False},
            {"$set": {"leido": True}}
        )

    #obtener la lista de todos los chats para la barra lateral
    conversaciones = obtener_conversaciones()

    mensajes = []
    chat_actual = None

    #si el usuario ha hecho clic en un chat específico de la lista, buscar los msj de ese teléfono ordenados de más antiguo a
    #más reciente
    if telefono_seleccionado:
        mensajes = list(db.chats.find({"telefono": telefono_seleccionado}).sort("fecha", 1))

        if mensajes:
            chat_actual = {
                "telefono": telefono_seleccionado,
                "nombre": mensajes[0].get("nombre", "Cliente"),
                "atendido_por": mensajes[-1].get("atendido_por", "bot")
            }

    return render_template('chat_admin.html', conversaciones=conversaciones, mensajes=mensajes, chat_actual=chat_actual)


@web_blueprint.route('/chat/enviar', methods=['POST'])
def enviar_mensaje_admin():
    telefono = request.form.get('telefono')
    mensaje = request.form.get('mensaje')

    if telefono and mensaje:
        ultimo_chat = db.chats.find_one({"telefono": telefono})
        nombre_cliente = ultimo_chat.get("nombre", "Cliente") if ultimo_chat else "Cliente"

        db.chats.insert_one({
            "telefono": telefono,
            "nombre": nombre_cliente,
            "mensaje": mensaje,
            "rol": "assistant",
            "atendido_por": "humano",
            "fecha": datetime.now()
        })

        cambiar_estado_chat(telefono, 'humano')

    return redirect(url_for('web.chat_admin', telefono=telefono))


@web_blueprint.route('/chat/cambiar-estado', methods=['POST'])
def cambiar_estado():
    telefono = request.form.get('telefono')
    nuevo_estado = request.form.get('atendido_por')

    if telefono and nuevo_estado:
        cambiar_estado_chat(telefono, nuevo_estado)

    return redirect(url_for('web.chat_admin', telefono=telefono))


@web_blueprint.route('/eliminar-cita/<id>', methods=['POST'])
def eliminar_cita(id):
    eliminar_cita_db(id)
    return redirect('/')


@web_blueprint.route('/editar-cita/<id>', methods=['POST'])
def editar_cita(id):
    fecha_form = request.form.get('fecha')
    hora_form = request.form.get('hora')
    paciente_form = request.form.get('paciente')
    motivo_form = request.form.get('motivo')
    duracion_form = int(request.form.get('duracion', 30))

    #Verificar solapamiento al editar (Excluyendo el id actual de la cita)
    disponible, mensaje = verificar_disponibilidad(db, fecha_form, hora_form, duracion_form, cita_id_excluir=id)

    if not disponible:
        flash(f'⚠️ No se pudo editar: {mensaje}', 'warning')
        return redirect('/')

    #actualizar datos en mongodb
    hora_fin_form = calcular_hora_fin(hora_form, duracion_form)

    datos_actualizados = {
        "fecha": fecha_form,
        "hora": hora_form,
        "duracion_minutos": duracion_form,
        "hora_fin": hora_fin_form,
        "paciente": paciente_form,
        "motivo": motivo_form
    }

    actualizar_cita_db(id, datos_actualizados)
    flash('✅ Cita actualizada correctamente.', 'success')
    return redirect('/')


# ---------------------------------------------------------------------------
# ENDPOINTS JSON PARA TIEMPO REAL (polling desde JavaScript)
# No usamos WebSockets para mantenerlo simple: el navegador pregunta cada
# pocos segundos "¿hay algo nuevo?" y actualiza solo lo necesario sin recargar
# toda la página (así no se pierde el scroll ni el mensaje que estabas escribiendo).
# ---------------------------------------------------------------------------

@web_blueprint.route('/api/chats-atencion-humana')
def api_chats_atencion_humana():
    """Devuelve la lista actual de conversaciones en modo 'humano', para que el
    dashboard refresque la tarjeta de alerta sin recargar toda la página."""
    conversaciones = obtener_conversaciones()
    urgentes = [c for c in conversaciones if c.get('atendido_por') == 'humano']
    data = [
        {
            "telefono": c.get("telefono"),
            "nombre": c.get("nombre") or c.get("telefono"),
            "ultimo_mensaje": c.get("ultimo_mensaje", "")
        }
        for c in urgentes
    ]
    return jsonify({"chats": data, "total": len(data)})


@web_blueprint.route('/chat/api/mensajes')
def chat_api_mensajes():
    """Devuelve los mensajes nuevos de una conversación desde un cierto _id en
    adelante (after_id), para que el panel de chat los añada en vivo sin que la
    veterinaria tenga que darle a 'actualizar' cada vez."""
    telefono = request.args.get('telefono')
    after_id = request.args.get('after_id')

    if not telefono:
        return jsonify({"error": "falta telefono"}), 400

    filtro = {"telefono": telefono}
    if after_id:
        try:
            filtro["_id"] = {"$gt": ObjectId(after_id)}
        except Exception:
            pass  # after_id inválido: devolvemos todos los mensajes de este teléfono

    nuevos = list(db.chats.find(filtro).sort("_id", 1))

    # Si estamos consultando esta conversación es porque se está viendo en
    # pantalla, así que aprovechamos para marcar como leídos sus mensajes.
    db.chats.update_many(
        {"telefono": telefono, "rol": "user", "leido": False},
        {"$set": {"leido": True}}
    )

    ultimo_estado = db.chats.find_one({"telefono": telefono}, sort=[("fecha", -1)])
    atendido_por_actual = ultimo_estado.get("atendido_por", "bot") if ultimo_estado else "bot"

    mensajes_json = [
        {
            "id": str(m["_id"]),
            "rol": m.get("rol"),
            "mensaje": m.get("mensaje", ""),
            "atendido_por": m.get("atendido_por", "bot"),
            "nombre": m.get("nombre", "Cliente")
        }
        for m in nuevos
    ]

    return jsonify({
        "mensajes": mensajes_json,
        "atendido_por_actual": atendido_por_actual
    })


@web_blueprint.route('/chat/api/conversaciones')
def chat_api_conversaciones():
    """Devuelve la lista de conversaciones (barra lateral) para refrescar los
    últimos mensajes, el modo (bot/humano) y el contador de no leídos en vivo."""
    conversaciones = obtener_conversaciones()
    data = [
        {
            "telefono": c.get("telefono"),
            "nombre": c.get("nombre") or c.get("telefono"),
            "ultimo_mensaje": c.get("ultimo_mensaje", ""),
            "atendido_por": c.get("atendido_por", "bot"),
            "sin_leer": c.get("sin_leer", 0)
        }
        for c in conversaciones
    ]
    return jsonify({"conversaciones": data})