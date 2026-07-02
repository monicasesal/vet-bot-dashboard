# Rutas de la página web (bento grid) // Blueprint = Router

from flask import Blueprint, render_template, request, redirect
from database.conexion import db

web_blueprint = Blueprint('web', __name__)

@web_blueprint.route('/')
def inicio():
    #traer los datos de la bd
    citas_desde_mongo = list(db.citas.find())
    chats_desde_mongo = list(db.chats.find())
    return render_template('index.html', mis_citas=citas_desde_mongo, los_chats=chats_desde_mongo)

@web_blueprint.route('/nueva-cita', methods=['POST'])
def nueva_cita():
    #capturar datos del form HTML
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