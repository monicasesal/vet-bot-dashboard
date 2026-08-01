# Conecta la BD y exporta db

import os
from pymongo import MongoClient
from dotenv import load_dotenv
from bson.objectid import ObjectId

load_dotenv()

cliente = MongoClient(os.getenv("MONGO_URI"), tls=True, tlsAllowInvalidCertificates=True) #Esto cambiar para PRODUCCION, no es seguro!

db = cliente["vetbot_db"]

# FUNCIONES DE CHATS

def obtener_conversaciones():
    """Devuelve la lista con el último mensaje primero"""
    pipeline = [
        {"$sort": {"fecha": 1}},  # Ordena mensajes por fecha ascendente primero
        {
            "$group": {
                "_id": "$telefono",
                "telefono": {"$first": "$telefono"},
                "nombre": {"$last": "$nombre"},
                "ultimo_mensaje": {"$last": "$mensaje"},
                "ultima_fecha": {"$last": "$fecha"},
                "atendido_por": {"$last": "$atendido_por"},
                "sin_leer": {
                    "$sum": {
                        "$cond": [
                            {"$and": [{"$eq": ["$leido", False]}, {"$eq": ["$rol", "user"]}]},
                            1,
                            0
                        ]
                    }
                }
            }
        },
        {"$sort": {"ultima_fecha": -1}}  # Sube los chats con mensajes más recientes ARRIBA
    ]
    return list(db.chats.aggregate(pipeline))


def cambiar_estado_chat(telefono, nuevo_estado):
    """Actualiza el campo atendido_por para todas las interacciones de un telefono"""
    db.chats.update_many(
        {"telefono": telefono},
        {"$set": {"atendido_por": nuevo_estado}}
    )

# FUNCIONES DE CITAS

def agregar_cita_db(datos_cita):
    """Inserta una nueva cita en MongoDB"""
    return db.citas.insert_one(datos_cita)

def eliminar_cita_db(cita_id):
    """Elimina una cita por su ID de MongoDB"""
    db.citas.delete_one({"_id": ObjectId(cita_id)})

def actualizar_cita_db(cita_id, datos_actualizados):
    """Actualiza los datos de una cita existente"""
    db.citas.update_one({"_id": ObjectId(cita_id)}, {"$set": datos_actualizados})

