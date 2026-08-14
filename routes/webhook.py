# Rutas para el bot de Whatsapp

from flask import Blueprint, request, jsonify
from database.conexion import db, guardar_cita_bd, cancelar_cita_bd, cambiar_cita_bd, obtener_citas_activas
from services.ia import generar_respuesta_veterinaria
from utils.citas_utils import verificar_disponibilidad, estimar_duracion_por_motivo
from config_horario import hora_apertura, hora_cierre
from datetime import datetime
import re

webhook_blueprint = Blueprint('webhook', __name__)


def _es_placeholder(valor):
    """Detecta si el modelo ha rellenado un campo con un placeholder genérico
    en vez de un dato real (p.ej. 'nombre_mascota', 'nombre_gato', 'motivo', 'N/A')."""
    if not valor:
        return True
    v = valor.strip().lower()
    placeholders_exactos = {
        "nombre_mascota", "mascota", "nombre de la mascota", "motivo",
        "n/a", "na", "desconocido", "pendiente", "sin especificar", "-"
    }
    if v in placeholders_exactos:
        return True
    if re.match(r'^nombre_\w+$', v):
        return True
    return False


def _buscar_cita_por_mascota(citas_activas, mascota):
    """Busca en la lista de citas activas de este teléfono la que corresponde
    a una mascota concreta (comparación insensible a mayúsculas/acentos simples)."""
    if not mascota:
        return None
    mascota_norm = mascota.strip().lower()
    for c in citas_activas:
        if c.get("mascota", "").strip().lower() == mascota_norm:
            return c
    return None


def _construir_confirmacion(accion, fecha, hora, mascota=None, motivo=None, duracion_minutos=None):
    """Genera el mensaje de confirmación a partir de datos REALES ya guardados
    en MongoDB, en vez de confiar en que el texto libre del modelo sea fiel a lo
    que se guardó. Así el cliente siempre ve lo que de verdad hay en la BD."""
    mascota_txt = f" de {mascota}" if mascota else ""
    if accion == "guardar":
        dur_txt = f" (duración estimada: {duracion_minutos} min)" if duracion_minutos else ""
        return (f"¡Perfecto! Te agendo la cita para el {fecha} a las {hora} "
                f"({mascota} - {motivo}){dur_txt}. ¡Te esperamos! 😊")
    if accion == "cambiar":
        return f"Listo, la cita{mascota_txt} ha quedado para el {fecha} a las {hora}. ¡Te esperamos! 😊"
    if accion == "cancelar":
        return f"Listo, la cita{mascota_txt} ha sido cancelada. ¡Que os vaya bien! 😊"
    return None


@webhook_blueprint.route('/webhook', methods=['POST'])
def recibir_mensaje():
    datos = request.get_json() or {}
    print('MENSAJE ENTRANTE DESDE WHATSAPP:', datos)

    nombre_usuario = datos.get('nombre', 'Usuario Anónimo')
    texto_mensaje = datos.get('mensaje', '')
    telefono_usuario = datos.get('telefono', 'Desconocido')

    fecha_actual = datetime.now()

    # 1. Consultar el estado actual del chat (si lo atiende bot o humano)
    ultimo_estado = db.chats.find_one(
        {"telefono": telefono_usuario},
        sort=[("fecha", -1)]
    )
    atendido_por = ultimo_estado.get("atendido_por", "bot") if ultimo_estado else "bot"

    # 2. Guardar el mensaje que envía el usuario
    nuevo_chat_usuario = {
        "telefono": telefono_usuario,
        "nombre": nombre_usuario,
        "mensaje": texto_mensaje,
        "rol": "user",
        "atendido_por": atendido_por,
        "leido": False,
        "fecha": fecha_actual
    }
    db.chats.insert_one(nuevo_chat_usuario)

    # Si la conversación la atiende un HUMANO, el bot se queda en silencio
    if atendido_por == "humano":
        print(f"[DEBUG] {telefono_usuario} está en modo HUMANO -> el bot no responde (silencio intencionado)")
        return jsonify({
            "status": "success",
            "message": "Mensaje registrado. En espera de respuesta del veterinario humano.",
            "atendido_por": "humano"
        }), 200

    # 3. Obtener el historial previo de la conversación (últimos 20 mensajes)
    historial_cursor = db.chats.find({"telefono": telefono_usuario}).sort("fecha", -1).limit(20)
    historial = list(historial_cursor)[::-1]
    historial_previo = historial[:-1] if len(historial) > 1 else []

    # 3b. TODAS las citas activas de este cliente (puede tener varias mascotas)
    citas_activas = obtener_citas_activas(telefono_usuario)

    # 4. Generar la respuesta con la IA
    respuesta_ia = generar_respuesta_veterinaria(
        mensaje_actual=texto_mensaje,
        historial_mensajes=historial_previo,
        citas_activas=citas_activas
    )

    # LOG DE DEPURACIÓN: texto crudo del modelo, ANTES de limpiar etiquetas.
    print(f"\n--- [DEBUG] RESPUESTA CRUDA DE LA IA para {telefono_usuario} ---")
    print(respuesta_ia)
    print("--- [FIN DEBUG] ---\n")

    # 5. Evaluar y limpiar la etiqueta de transferencia a humano
    if "TRANSFERIR_HUMANO" in respuesta_ia:
        atendido_por = "humano"
        respuesta_ia = re.sub(r'\[?TRANSFERIR_HUMANO\]?\.?', '', respuesta_ia).strip()
        if not respuesta_ia:
            respuesta_ia = "Entendido. Un momento por favor, le transfiero la conversación con nuestro equipo veterinario."

    # 6. Detectar órdenes enviadas por la IA y ejecutarlas en MongoDB.
    respuesta_final = None

    # A) AGENDAR CITA(S) NUEVA(S) - FIX: antes usábamos re.search, que solo encuentra
    # LA PRIMERA etiqueta. Cuando el cliente agenda varias mascotas a la vez, el modelo
    # genera una etiqueta [GUARDAR_CITA...] por mascota en el mismo mensaje, y todas
    # menos la primera se perdían en silencio. Ahora procesamos TODAS con re.finditer.
    matches_guardar = list(re.finditer(
        r'\[GUARDAR_CITA:\s*([\d-]+)\s*\|\s*([\d:]+)\s*\|\s*([^|]+)\s*\|\s*([^\]]+)\]', respuesta_ia
    ))
    mensajes_guardado = []
    for match_guardar in matches_guardar:
        if "HH:MM" in match_guardar.group(2):
            continue  # placeholder de plantilla sin rellenar, lo ignoramos directamente

        fecha_res = match_guardar.group(1).strip()
        hora_res = match_guardar.group(2).strip()
        mascota_res = match_guardar.group(3).strip()
        motivo_res = match_guardar.group(4).strip()

        duracion_estimada = estimar_duracion_por_motivo(motivo_res)

        disponible, msg_disp = verificar_disponibilidad(db, fecha_res, hora_res, duracion_estimada)
        print(f"[DEBUG] verificar_disponibilidad(GUARDAR mascota={mascota_res!r}) fecha={fecha_res} "
              f"hora={hora_res} duracion={duracion_estimada} -> {disponible} | {msg_disp}")

        if _es_placeholder(mascota_res) or _es_placeholder(motivo_res):
            print(f"[DEBUG] GUARDAR_CITA rechazado por placeholders: mascota='{mascota_res}' motivo='{motivo_res}'")
            faltan = []
            if _es_placeholder(mascota_res):
                faltan.append("el nombre de la mascota")
            if _es_placeholder(motivo_res):
                faltan.append("el motivo de la consulta")
            mensajes_guardado.append(
                f"Antes de confirmar la cita del {fecha_res} a las {hora_res}, me falta {' y '.join(faltan)} 😊"
            )
        elif disponible:
            # guardar_cita_bd ya solo reemplaza la cita de ESTA mascota concreta,
            # sin tocar las citas de otras mascotas del mismo teléfono.
            guardar_cita_bd(
                nombre_cliente=nombre_usuario,
                telefono=telefono_usuario,
                fecha_str=fecha_res,
                hora_str=hora_res,
                mascota=mascota_res,
                motivo=motivo_res,
                duracion_minutos=duracion_estimada
            )
            mensajes_guardado.append(
                _construir_confirmacion("guardar", fecha_res, hora_res, mascota_res, motivo_res, duracion_estimada)
            )
        else:
            mensajes_guardado.append(
                f"¡Uy! Justo se ha ocupado la hora {hora_res} del {fecha_res} para {mascota_res} 😅 "
                "¿Me dices otro día u hora para esa mascota y te lo confirmo?"
            )

    if mensajes_guardado:
        respuesta_final = "\n\n".join(mensajes_guardado)

    # B) CANCELAR CITA(S) - ahora incluye qué mascota, o "TODAS". Procesamos TODAS las
    # etiquetas presentes (igual que en GUARDAR_CITA) por si cancela varias a la vez.
    matches_cancelar = list(re.finditer(r'\[CANCELAR_CITA:\s*([^\]]+)\]', respuesta_ia))
    mensajes_cancelar = []
    for match_cancelar in matches_cancelar:
        mascota_canc = match_cancelar.group(1).strip()
        mascota_para_filtro = None if mascota_canc.upper() == "TODAS" else mascota_canc

        exito_cancelar = cancelar_cita_bd(telefono=telefono_usuario, mascota=mascota_para_filtro)
        print(f"[DEBUG] cancelar_cita_bd(mascota={mascota_para_filtro!r}) -> {exito_cancelar}")
        if exito_cancelar:
            mensajes_cancelar.append(_construir_confirmacion("cancelar", None, None, mascota=mascota_para_filtro))
        else:
            quien = f"de {mascota_canc}" if mascota_para_filtro else ""
            mensajes_cancelar.append(
                f"No he encontrado ninguna cita activa {quien} a tu nombre para cancelar 🤔".replace("  ", " ")
            )

    if mensajes_cancelar:
        respuesta_final = "\n\n".join(mensajes_cancelar)

    # C) CAMBIAR CITA(S) - ahora incluye qué mascota para saber cuál de las citas mover.
    # Formato esperado: [CAMBIAR_CITA: mascota | YYYY-MM-DD | HH:MM]. Procesamos TODAS
    # las etiquetas presentes, igual que en GUARDAR_CITA.
    matches_cambiar = list(re.finditer(
        r'\[CAMBIAR_CITA:\s*([^|]+)\s*\|\s*([\d-]+)\s*\|\s*([\d:]+)\]', respuesta_ia
    ))
    mensajes_cambiar = []
    for match_cambiar in matches_cambiar:
        mascota_cambio = match_cambiar.group(1).strip()
        fecha_nueva = match_cambiar.group(2).strip()
        hora_nueva = match_cambiar.group(3).strip()

        cita_a_cambiar = _buscar_cita_por_mascota(citas_activas, mascota_cambio)
        motivo_cita = cita_a_cambiar.get("motivo") if cita_a_cambiar else None
        duracion_estimada_cambio = estimar_duracion_por_motivo(motivo_cita)

        cita_id_excluir = str(cita_a_cambiar["_id"]) if cita_a_cambiar else None
        disponible, msg_disp = verificar_disponibilidad(
            db, fecha_nueva, hora_nueva, duracion_estimada_cambio, cita_id_excluir=cita_id_excluir
        )
        print(f"[DEBUG] verificar_disponibilidad(CAMBIAR mascota={mascota_cambio!r}) fecha={fecha_nueva} "
              f"hora={hora_nueva} duracion={duracion_estimada_cambio} -> {disponible} | {msg_disp}")

        if disponible:
            exito = cambiar_cita_bd(
                telefono=telefono_usuario,
                mascota=mascota_cambio,
                fecha_nueva=fecha_nueva,
                hora_nueva=hora_nueva,
                duracion_minutos=duracion_estimada_cambio
            )
            if not exito:
                motivo_fallback = motivo_cita or "Consulta veterinaria"
                guardar_cita_bd(
                    nombre_cliente=nombre_usuario,
                    telefono=telefono_usuario,
                    fecha_str=fecha_nueva,
                    hora_str=hora_nueva,
                    mascota=mascota_cambio,
                    motivo=motivo_fallback,
                    duracion_minutos=duracion_estimada_cambio
                )
            mensajes_cambiar.append(
                _construir_confirmacion("cambiar", fecha_nueva, hora_nueva, mascota=mascota_cambio)
            )
        else:
            mensajes_cambiar.append(
                f"Vaya, la nueva hora ({hora_nueva} del {fecha_nueva}) para {mascota_cambio} ya está ocupada 😅 "
                "¿Qué otro día u hora te vendría bien para esa mascota?"
            )

    if mensajes_cambiar:
        respuesta_final = "\n\n".join(mensajes_cambiar)

    # 7. Limpiar etiquetas del texto original del modelo
    respuesta_ia = re.sub(r'\[(GUARDAR_CITA|CANCELAR_CITA|CAMBIAR_CITA)[^\]]*\]', '', respuesta_ia).strip()

    # 7c. RED DE SEGURIDAD: el modelo a veces dice que una hora CONCRETA está
    # "cerrada" u "ocupada" sin que eso sea cierto y sin generar una etiqueta válida.
    if not respuesta_final:
        match_rechazo = re.search(
            r'(\d{1,2}:\d{2}).{0,40}?(cerrad|ocupad|no\s+(?:hay|tenemos)\s+disponib)',
            respuesta_ia, re.IGNORECASE
        )
        if match_rechazo:
            hora_mencionada = match_rechazo.group(1)
            # Si solo tiene una mascota con cita activa, usamos su fecha/motivo como referencia
            # para adivinar fecha/duración; si tiene varias (o ninguna), usamos hoy y 30 min.
            cita_referencia = citas_activas[0] if len(citas_activas) == 1 else None
            fecha_objetivo = (cita_referencia.get("fecha") if cita_referencia else None) or datetime.now().strftime("%Y-%m-%d")
            dentro_horario = hora_apertura() <= hora_mencionada <= hora_cierre()

            if dentro_horario:
                duracion_check = estimar_duracion_por_motivo(cita_referencia.get("motivo") if cita_referencia else None)
                disponible_real, msg_disp = verificar_disponibilidad(
                    db, fecha_objetivo, hora_mencionada, duracion_check, cita_id_excluir=None
                )
                print(f"[DEBUG] Comprobando posible alucinación de 'cerrado/ocupado' a las {hora_mencionada} "
                      f"el {fecha_objetivo} -> disponible_real={disponible_real} | {msg_disp}")

                if disponible_real:
                    print(f"[DEBUG] Corrigiendo alucinación: el modelo dijo que {hora_mencionada} no estaba "
                          f"disponible, pero SÍ lo está. Respuesta original: {respuesta_ia!r}")
                    respuesta_ia = (
                        f"¡Perdona la confusión! Sí tengo hueco a las {hora_mencionada} 😊 "
                        "¿Confirmas que quieres la cita a esa hora?"
                    )
                else:
                    print(f"[DEBUG] Reescribiendo mensaje ambiguo de indisponibilidad a las {hora_mencionada}: "
                          f"{msg_disp}")
                    respuesta_ia = (
                        f"Lo siento, a las {hora_mencionada} ya tenemos otra cita reservada 😔 "
                        "(no estamos cerrados, es que justo ese hueco está ocupado). "
                        "¿Te viene bien otro horario?"
                    )

    # Si alguna acción de BD se ejecutó, esa es la respuesta que se envía al cliente
    if respuesta_final:
        respuesta_ia = respuesta_final

    # 7b. RED DE SEGURIDAD DE PRIVACIDAD
    patron_fuga_privacidad = re.compile(
        r'(ocupad[oa]\s+por\s+\w|cita\s+con\s+(?:un|una)\s+(?:perro|gato|mascota|paciente)|'
        r'perro\s+llamad[oa]|gat[oa]\s+llamad[oa]|mascota\s+llamad[oa]|paciente\s+llamad[oa])',
        re.IGNORECASE
    )
    if patron_fuga_privacidad.search(respuesta_ia):
        print(f"[DEBUG] Posible fuga de privacidad detectada y bloqueada en: {respuesta_ia!r}")
        respuesta_ia = (
            "Por privacidad no puedo compartir los datos de otros clientes 😊 "
            "Lo que sí te puedo confirmar es que ese horario está ocupado. "
            "¿Te va bien alguno de los otros horarios libres?"
        )

    # 8. Guardar la respuesta dada por la IA en la BBDD
    nuevo_chat_bot = {
        "telefono": telefono_usuario,
        "nombre": nombre_usuario,
        "mensaje": respuesta_ia,
        "rol": "assistant",
        "atendido_por": atendido_por,
        "leido": True,
        "fecha": datetime.now()
    }
    db.chats.insert_one(nuevo_chat_bot)

    return jsonify({
        "status": "success",
        "message": "Mensaje procesado",
        "respuesta_bot": respuesta_ia,
        "atendido_por": atendido_por
    }), 200