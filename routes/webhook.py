# Rutas para el bot de Whatsapp

from flask import Blueprint, request, jsonify
from services.ia import generar_respuesta_veterinaria
from database.conexion import db

webhook_blueprint = Blueprint('webhook', __name__)

@webhook_blueprint.route('/webhook', methods=['POST'])
def recibir_mensaje():
    datos = request.get_json() #Meta envía ls msj en formato JSON, no en formulario
    print('MENSAJE ENTRANTE DESDE WHTSPP:', datos)

    nombre_usuario = datos.get('nombre', 'Usuario Anónimo')
    texto_mensaje = datos.get('mensaje', '')

    #Guardar el msj que envía el usuario
    nuevo_chat_usuario = {
        "usuario": nombre_usuario,
        "mensaje": texto_mensaje,
        "rol": "user", #lo envía el cliente
        "fecha": "2026-07-02"
    }

    db.chats.insert_one(nuevo_chat_usuario)

    #Pasar el msj a la IA para que genere la respuesta
    respuesta_ia = generar_respuesta_veterinaria(texto_mensaje)

    #Guardar la respuesta que ha dado la IA en la bbdd
    nuevo_chat_bot = {
        "usuario": "VetBot",
        "mensaje": respuesta_ia,
        "rol": "assistant",
        "fecha": "2026-07-02"
    }
    db.chats.insert_one(nuevo_chat_bot)

    #Devolver a Postman la respuesta para poder verla en pantalla
    return jsonify({
        "status": "success",
        "message": "Mensaje procesado",
        "respuesta_bot": respuesta_ia
    }), 200