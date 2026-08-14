# lógica matemática para detectar solapamientos

from datetime import datetime, timedelta
from config_horario import BLOQUES_HORARIO, describir_horario_texto

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

def _dentro_horario_clinica(hora_inicio, hora_fin):
    """Comprueba que el intervalo [hora_inicio, hora_fin) cae ENTERO dentro de un
    único bloque de apertura de la clínica (definidos en config_horario.py),
    sin cruzar pausas entre bloques ni pasarse del cierre."""
    ini = datetime.strptime(hora_inicio, FORMATO_HORA)
    fin = datetime.strptime(hora_fin, FORMATO_HORA)

    for inicio_bloque_str, fin_bloque_str in BLOQUES_HORARIO:
        inicio_bloque = datetime.strptime(inicio_bloque_str, FORMATO_HORA)
        fin_bloque = datetime.strptime(fin_bloque_str, FORMATO_HORA)
        if ini >= inicio_bloque and fin <= fin_bloque:
            return True
    return False


def verificar_disponibilidad(db, fecha, hora_inicio, duracion_minutos=30, cita_id_excluir=None):
    """
    Consulta en MongoDB si existe alguna cita que se solape en esa fecha, Y comprueba
    que la cita entera (inicio + duración) cae dentro del horario real de la clínica
    (sin cruzar la pausa de comida 13:00-15:00 ni pasarse del cierre a las 20:30 ni
    empezar antes de las 09:00).
    Opcionalmente excluye 'cita_id_excluir' por si estamos editando una cita existente.
    """
    hora_fin_nueva = calcular_hora_fin(hora_inicio, duracion_minutos)

    if not _dentro_horario_clinica(hora_inicio, hora_fin_nueva):
        return False, (
            f"La cita de {hora_inicio} a {hora_fin_nueva} se sale del horario de la clínica "
            f"({describir_horario_texto()})"
        )

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


# NUEVO: mapea el motivo de consulta a una duración estimada en minutos.
# Usa las mismas categorías que ya tienes en el <select> del panel web
# (form-agendar-grid), para que la duración que "adivina" el bot de WhatsApp
# sea coherente con lo que un humano elegiría manualmente en el panel.
DURACIONES_POR_PALABRA_CLAVE = [
    (90, ["cirugia mayor", "cirugía mayor"]),
    (60, ["cirugia", "cirugía", "procedimiento", "operacion", "operación"]),
    (45, ["ecografia", "ecografía", "compleja", "complicad", "radiografia", "radiografía", "analitica", "analítica"]),
    (15, ["vacuna", "vacunacion", "vacunación", "revision rapida", "revisión rápida",
          "chequeo rapido", "chequeo rápido", "desparasitacion", "desparasitación",
          "corte de unas", "corte de uñas", "microchip"]),
]

def estimar_duracion_por_motivo(motivo, duracion_por_defecto=30):
    """Devuelve la duración estimada en minutos según palabras clave del motivo.
    Si no reconoce ninguna palabra clave, devuelve 30 (consulta general),
    igual que el valor 'selected' por defecto del formulario web."""
    if not motivo:
        return duracion_por_defecto

    motivo_lower = motivo.lower()
    for duracion, palabras_clave in DURACIONES_POR_PALABRA_CLAVE:
        if any(palabra in motivo_lower for palabra in palabras_clave):
            return duracion

    return duracion_por_defecto