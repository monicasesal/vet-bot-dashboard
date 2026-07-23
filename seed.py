import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Conectar a MongoDB Atlas
cliente = MongoClient(os.getenv("MONGO_URI"))
db = cliente["vetbot_db"]

print("Conectando a MongoDB para insertar datos...")

fecha_hoy = datetime.now().strftime('%Y-%m-%d')

# Datos de prueba para las Citas
nuevas_citas = [
    {"fecha": fecha_hoy, "hora": "09:00", "paciente": "Max (Desde Mongo)", "motivo": "Revisión Cachorro"},
    {"fecha": fecha_hoy, "hora": "12:15", "paciente": "Kira (Desde Mongo)", "motivo": "Esterilización"},
    {"fecha": fecha_hoy, "hora": "17:30", "paciente": "Copito (Desde Mongo)", "motivo": "Corte de dientes"}
]

# Datos de prueba para los Chats de la IA
nuevos_chats = [
    {
        "telefono": "+34600111222",
        "nombre": "Roberto (Dueño de Max)", 
        "mensaje": "Ya vamos de camino a la clínica", 
        "rol": "user",
        "atendido_por": "bot",
        "fecha": datetime.now()
    },
    {
        "telefono": "+34600333444",
        "nombre": "Lucía (Dueña de Kira)",
        "mensaje": "¿A qué hora tengo que dejarla en ayunas?",
        "rol": "user",
        "atendido_por": "humano",
        "fecha": datetime.now()    
    },
    {
        "telefono": "+34600555666",
        "nombre": "Pedro (Dueño de Copito)",
        "mensaje": "Todo perfecto, gracias",
        "rol": "user",
        "atendido_por": "bot",
        "fecha": datetime.now()    
    }
]

# Borrar lo que hubiera antes para no duplicar y guardar los nuevos datos
db.citas.drop()
db.chats.drop()

db.citas.insert_many(nuevas_citas)
db.chats.insert_many(nuevos_chats)

print("Datos insertados con éxito en la nube")