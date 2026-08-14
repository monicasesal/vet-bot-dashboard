# Conecta la BD y exporta db

import os
from pymongo import MongoClient
from dotenv import load_dotenv
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from utils.citas_utils import calcular_hora_fin, hay_solapamiento 
from config_horario import BLOQUES_HORARIO, DIAS_CERRADOS, PASO_MINUTOS_AGENDA

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

def obtener_horarios_disponibles(fecha_str, duracion_minutos=30):
    """Dada una fecha en formato YYYY-MM-DD, devuelve las horas libres.

    FIX: antes usaba una lista fija de horas en punto y comparaba por
    coincidencia EXACTA de string contra 'hora' - eso hacía que huecos como
    10:30 nunca se ofrecieran (no estaban en la lista) aunque estuvieran
    realmente libres. Ahora genera huecos cada 15 minutos (el mínimo común de
    las duraciones posibles: 15/30/45/60/90) dentro del horario de la clínica
    (09:00-13:00 y 15:00-20:30, con pausa de comida) y comprueba SOLAPAMIENTO
    REAL contra las citas existentes (con su duración), igual que hace
    verificar_disponibilidad() en citas_utils.py - y ahora respeta la
    'duracion_minutos' concreta que se le pida (una vacunación de 15 min
    puede caber en un hueco donde una cirugía de 60 min no cabría).
    """
    bloques = BLOQUES_HORARIO  # viene de config_horario.py, un único sitio para editar el horario
    PASO_MINUTOS = PASO_MINUTOS_AGENDA

    citas_ocupadas = list(db.citas.find({"fecha": fecha_str}))

    # si la fecha consultada es HOY, no ofrecer horas que ya han pasado
    ahora = datetime.now()
    es_hoy = (fecha_str == ahora.strftime("%Y-%m-%d"))
    hora_actual_dt = ahora if es_hoy else None

    horas_libres = []
    for inicio_bloque, fin_bloque in bloques:
        actual = datetime.strptime(inicio_bloque, "%H:%M")
        fin_bloque_dt = datetime.strptime(fin_bloque, "%H:%M")

        while actual + timedelta(minutes=duracion_minutos) <= fin_bloque_dt:
            hora_candidata = actual.strftime("%H:%M")

            # Si es hoy, descartamos huecos que ya hayan pasado
            if es_hoy:
                candidata_dt = ahora.replace(
                    hour=actual.hour, minute=actual.minute, second=0, microsecond=0
                )
                if candidata_dt <= hora_actual_dt:
                    actual += timedelta(minutes=PASO_MINUTOS)
                    continue

            hora_fin_candidata = calcular_hora_fin(hora_candidata, duracion_minutos)

            libre = True
            for c in citas_ocupadas:
                duracion_existente = c.get("duracion_minutos", 30)
                hora_fin_existente = c.get("hora_fin") or calcular_hora_fin(c["hora"], duracion_existente)
                if hay_solapamiento(hora_candidata, hora_fin_candidata, c["hora"], hora_fin_existente):
                    libre = False
                    break

            if libre:
                horas_libres.append(hora_candidata)

            actual += timedelta(minutes=PASO_MINUTOS)

    return horas_libres


def obtener_agenda_proximos_dias(dias=7, duracion_minutos=30):
    """
    Devuelve un texto con el calendario real de los próximos X días,
    indicando el día de la semana, la fecha exacta y las horas libres en MongoDB
    PARA LA DURACIÓN INDICADA (por defecto 30 min, "consulta general").
    """
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    hoy = datetime.now()
    resumen_agenda = "\n--- AGENDA REAL DE LA CLÍNICA (SISTEMA DE CITAS) ---\n"
    resumen_agenda += f"(Huecos calculados para una duración de cita de {duracion_minutos} minutos)\n"

    for i in range(dias):
        fecha_obj = hoy + timedelta(days=i)
        fecha_str = fecha_obj.strftime("%Y-%m-%d")
        nombre_dia = dias_semana[fecha_obj.weekday()]

        # Obtenemos las horas libres reales de la BBDD para esta duración concreta
        horas_libres = obtener_horarios_disponibles(fecha_str, duracion_minutos=duracion_minutos)

        if fecha_obj.weekday() in DIAS_CERRADOS:
            resumen_agenda += f"- {nombre_dia} {fecha_str}: CERRADO.\n"
        elif horas_libres:
            resumen_agenda += f"- {nombre_dia} {fecha_str}: Horarios libres -> {', '.join(horas_libres)}\n"
        else:
            resumen_agenda += f"- {nombre_dia} {fecha_str}: SIN CITAS DISPONIBLES (Agenda llena).\n"

    resumen_agenda += "-----------------------------------------------------\n"
    return resumen_agenda


def obtener_citas_activas(telefono):
    """Devuelve TODAS las citas activas de un teléfono (puede tener varias, una
    por mascota). Sustituye a la antigua obtener_cita_activa, que solo devolvía
    una y por eso el sistema no soportaba más de una mascota por cliente."""
    return list(db.citas.find({"telefono": telefono}))


def obtener_cita_activa(telefono):
    """Devuelve la primera cita activa encontrada para un teléfono.
    Mantenida para retrocompatibilidad con funciones que solo esperan un único documento"""
    return db.citas.find_one({"telefono": telefono})


def guardar_cita_bd(nombre_cliente, telefono, fecha_str, hora_str, mascota, motivo, duracion_minutos=30):
    """Guarda una cita para UNA mascota concreta de este teléfono.

    FIX: antes borraba TODAS las citas del teléfono antes de insertar, así que
    un cliente con 2 mascotas perdía la cita de la primera al agendar la
    segunda. Ahora solo reemplaza la cita anterior de ESA MISMA mascota (por si
    el cliente cambia de opinión sobre la cita de su perro, por ejemplo), sin
    tocar las citas de sus otras mascotas.
    """
    db.citas.delete_many({"telefono": telefono, "mascota": mascota})

    hora_fin_str = calcular_hora_fin(hora_str, duracion_minutos)

    nueva_cita = {
        "nombre": nombre_cliente,
        "telefono": telefono,
        "fecha": fecha_str,
        "hora": hora_str,
        "duracion_minutos": duracion_minutos,
        "hora_fin": hora_fin_str,
        "mascota": mascota,
        "motivo": motivo,
        "creado_por": "bot",
        "fecha_creacion": datetime.now()
    }
    db.citas.insert_one(nueva_cita)
    print(f" Cita guardada para {mascota} ({telefono}) el {fecha_str} a las {hora_str}")


def cambiar_cita_bd(telefono, mascota, fecha_nueva, hora_nueva, duracion_minutos=30):
    """Actualiza la cita de UNA mascota concreta de este teléfono a la nueva
    fecha y hora. FIX: antes buscaba 'la' cita del teléfono sin más (find_one),
    lo cual era ambiguo si había varias mascotas - ahora exige mascota para
    saber cuál de las citas del cliente hay que mover.
    NOTA: esta función NO comprueba solapamientos, eso se hace en webhook.py
    antes de llamarla.
    """
    cita = db.citas.find_one({"telefono": telefono, "mascota": mascota})
    if cita:
        hora_fin_str = calcular_hora_fin(hora_nueva, duracion_minutos)
        db.citas.update_one(
            {"_id": cita["_id"]},
            {"$set": {
                "fecha": fecha_nueva,
                "hora": hora_nueva,
                "duracion_minutos": duracion_minutos,
                "hora_fin": hora_fin_str,
                "fecha_modificacion": datetime.now()
            }}
        )
        print(f" Cita de {mascota} actualizada a {fecha_nueva} {hora_nueva}")
        return True
    return False


def cancelar_cita_bd(telefono, mascota=None, fecha_str=None):
    """Borra la cita de UNA mascota concreta de este teléfono.
    FIX: antes borraba TODAS las citas del teléfono (delete_many sin filtrar
    por mascota), lo que cancelaría por error la cita de otra mascota del
    mismo cliente. Si no se especifica mascota (compatibilidad hacia atrás,
    o cliente con una sola cita activa), mantiene el comportamiento antiguo.
    """
    filtro = {"telefono": telefono}
    if mascota:
        filtro["mascota"] = mascota
    res = db.citas.delete_many(filtro)
    if res.deleted_count > 0:
        print(f" Cita eliminada para el teléfono {telefono} (mascota={mascota})")
        return True
    return False