# Rutas de la página web (bento grid) // Blueprint = Router

from flask import Blueprint, render_template, request, redirect, url_for
from urllib.parse import unquote
from database.conexion import db, obtener_conversaciones, cambiar_estado_chat
from datetime import datetime

web_blueprint = Blueprint('web', __name__)


@web_blueprint.route('/')
def inicio():
    #muestra la pag principal cargando todas las citas y chats desde MongoDB
    citas_desde_mongo = list(db.citas.find())
    chats_desde_mongo = list(db.chats.find())
    return render_template('index.html', mis_citas=citas_desde_mongo, los_chats=chats_desde_mongo)

@web_blueprint.route('/nueva-cita', methods=['POST'])
def nueva_cita():
    #recibe los datos del form, crea una nueva cita, la guarda en MongoDB y redirige a la pag principal
    hora_form = request.form.get('hora')
    paciente_form = request.form.get('paciente')
    motivo_form = request.form.get('motivo')

    cita_nueva = {
        "hora": hora_form,
        "paciente": paciente_form,
        "motivo": motivo_form
    }

    #insertar en la colección correspondiente
    db.citas.insert_one(cita_nueva)
    return redirect('/')

@web_blueprint.route('/chat')
def chat_admin():
    telefono_raw = request.args.get('telefono')

    telefono_seleccionado = unquote(telefono_raw) if telefono_raw else None

    #obtener la lista de todos los chats para la barra lateral
    conversaciones = obtener_conversaciones()

    mensajes = []
    chat_actual = None

    #si el usuario ha hecho clic en un chat específico de la lista, buscar los msj de ese teléfono ordenados de más antiguo a 
    #más reciente
    if telefono_seleccionado:
        mensajes =  list(db.chats.find({"telefono": telefono_seleccionado}).sort("fecha", 1))

        if mensajes:
            chat_actual = {
                "telefono": telefono_seleccionado,
                "nombre": mensajes[0].get("nombre", "Cliente"),
                "atendido_por": mensajes[-1].get("atendido_por", "bot")
            }
        
    return render_template('chat.html', conversaciones=conversaciones, mensajes=mensajes, chat_actual=chat_actual)


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