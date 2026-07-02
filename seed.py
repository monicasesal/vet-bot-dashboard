import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Conectar a MongoDB Atlas
cliente = MongoClient(os.getenv("MONGO_URI"))
db = cliente["vetbot_db"]

print("Conectando a MongoDB para insertar datos...")

# Datos de prueba para las Citas
nuevas_citas = [
    {"hora": "09:00", "paciente": "Max (Desde Mongo)", "motivo": "Revisión Cachorro"},
    {"hora": "12:15", "paciente": "Kira (Desde Mongo)", "motivo": "Esterilización"},
    {"hora": "17:30", "paciente": "Copito (Desde Mongo)", "motivo": "Corte de dientes"}
]

# Datos de prueba para los Chats de la IA
nuevos_chats = [
    {"usuario": "Roberto (Dueño de Max)", "mensaje": "Ya vamos de camino a la clínica", "atendido_por": "IA"},
    {"usuario": "Lucía (Dueña de Kira)", "mensaje": "¿A qué hora tengo que dejarla en ayunas?", "atendido_por": "Humano"},
    {"usuario": "Pedro (Dueño de Copito)", "mensaje": "Todo perfecto, gracias", "atendido_por": "IA"}
]

# Borrar lo que hubiera antes para no duplicar y guardar los nuevos datos
db.citas.drop()
db.chats.drop()

db.citas.insert_many(nuevas_citas)
db.chats.insert_many(nuevos_chats)

print("¡Datos insertados con éxito en la nube!")