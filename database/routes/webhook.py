# Rutas para el bot de Whatsapp

from flask import Blueprint, request, jsonify
from database.conexion import db

webhook_blueprint = Blueprint('webhook', __name__)

@webhook_blueprint.route('/webhook', methods=['POST'])
def recibir_mensaje():
    datos = request.get_json() #Meta envía ls msj en formato JSON, no en formulario
    print('MENSAJE ENTRANTE DESDE WHTSPP:', datos)

    return jsonify({'status': 'success', 'message': 'Mensaje recibido'}), 200