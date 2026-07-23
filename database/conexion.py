# Conecta la BD y exporta db

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

cliente = MongoClient(os.getenv("MONGO_URI"), tls=True, tlsAllowInvalidCertificates=True) #Esto cambiar para PRODUCCION, no es seguro!

db = cliente["vetbot_db"]

# Funciones consulta de chats

def obtener_conversaciones():
    """Devuelve la lista de chats únicos con el último mensaje"""
    # Agrupar por usuario/teléfono para el panel lateral
    return list(db.chats.aggregate([
        {"$sort": {"fecha": -1}},
        {"$group": {
            "_id": "$telefono",
            "telefono": {"$first": "$telefono"},
            "nombre": {"$first": "$nombre"},
            "ultimo_mensaje": {"$first": "$mensaje"},
            "fecha": {"$first": "$fecha"},
            "atendido_por": {"$first": "$atendido_por"} #bot o humano

        }}
    ]))

def cambiar_estado_chat(telefono, nuevo_estado):
    """Actualiza el campo atendido_por para todas las interacciones de un telefono"""
    db.chats.update_many(
        {"telefono": telefono},
        {"$set": {"atendido_por": nuevo_estado}}
    )
