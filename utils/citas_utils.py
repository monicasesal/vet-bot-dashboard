# lógica matemática para detectar solapamientos

from datetime import datetime, timedelta

FORMATO_HORA = "%H:%M"

def calcular_hora_fin(hora_inicio_str, duracion_minutos=30):
    """Suma los minutos a la hora de inicio (HH:MM)."""
    inicio = datetime.strptime(hora_inicio_str, FORMATO_HORA)
    fin = inicio + timedelta(minutes=int(duracion_minutos))
    return fin.strftime(FORMATO_HORA)

def hay_solapamiento(inicio_A, fin_A, inicio_B, fin_B):
    """
    Compara dos rangos de horas (HH:MM).
    Devuelve True si se cruzan/solapan, False si no hay conflicto.
    Fórmula: InicioA < FinB y FinA > InicioB
    """
    iA = datetime.strptime(inicio_A, FORMATO_HORA)
    fA = datetime.strptime(fin_A, FORMATO_HORA)
    iB = datetime.strptime(inicio_B, FORMATO_HORA)
    fB = datetime.strptime(fin_B, FORMATO_HORA)

    return (iA < fB) and (fA > iB)

def verificar_disponibilidad(db, fecha, hora_inicio, duracion_minutos=30, cita_id_excluir=None):
    """
    Consulta en MongoDB si existe alguna cita que se solape en esa fecha.
    Opcionalmente excluye 'cita_id_excluir' por si estamos editando una cita existente.
    """
    hora_fin_nueva = calcular_hora_fin(hora_inicio, duracion_minutos)
    
    # Traer todas las citas de esa misma fecha
    citas_dia = list(db.citas.find({"fecha": fecha}))

    for cita in citas_dia:
        # Si estoy editando una cita, ignorar su propio ID
        if cita_id_excluir and str(cita.get('_id')) == str(cita_id_excluir):
            continue

        # Si la cita antigua no tiene duracion guardada aún, asumir 30 min por defecto
        duracion_existente = cita.get("duracion_minutos", 30)
        hora_fin_existente = cita.get("hora_fin") or calcular_hora_fin(cita["hora"], duracion_existente)

        # Probar la regla matemática de solapamiento
        if hay_solapamiento(hora_inicio, hora_fin_nueva, cita["hora"], hora_fin_existente):
            return False, f"Conflicto de horario con {cita.get('paciente', 'otra cita')} ({cita['hora']} - {hora_fin_existente})"

    return True, "Horario disponible"