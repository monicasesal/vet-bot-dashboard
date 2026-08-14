# ÚNICO SITIO que hay que tocar para adaptar el horario de la clínica. Todo lo demás (conexion.py, citas_utils.py, ia.py, webhook.py) bebe de aquí, así que cambiando esto se actualiza TODO el sistema de forma consistente:
# la disponibilidad real en Mongo, la agenda que se muestra al cliente, y las reglas que sigue la IA en el prompt.

# Bloques de apertura, en formato ("HH:MM", "HH:MM"). Puedo tener 1, 2 o más
# bloques (por ejemplo, sin pausa de comida sería un único bloque).
# Ejemplos:
#   Con pausa de comida:    [("09:00", "13:00"), ("15:00", "20:30")]
#   Sin pausa de comida:    [("09:00", "18:00")]
#   Turno partido distinto: [("08:00", "14:00"), ("16:00", "21:00")]
BLOQUES_HORARIO = [
    ("09:00", "13:00"),
    ("15:00", "20:30"),
]

# Días de la semana CERRADOS, según datetime.weekday(): 0=Lunes, 1=Martes,
# 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo.
# Ejemplo: clínica cerrada los domingos y lunes -> [0, 6]
DIAS_CERRADOS = [5, 6]  # Sábado y Domingo

# Granularidad (en minutos) con la que se generan los huecos de la agenda.
# Debe ser un divisor de todas las duraciones posibles que use (15/30/45/60/90
# minutos -> 15 es el mínimo común).
PASO_MINUTOS_AGENDA = 15


def hora_apertura():
    """Hora a la que abre la clínica (el inicio del primer bloque)."""
    return BLOQUES_HORARIO[0][0]


def hora_cierre():
    """Hora a la que cierra la clínica (el fin del último bloque)."""
    return BLOQUES_HORARIO[-1][1]


def nombre_dia_cerrado(dias_semana_es):
    """Devuelve los nombres (en español) de los días cerrados, dada una lista
    de nombres de días indexada 0=Lunes...6=Domingo (la misma que ya usas en
    obtener_agenda_proximos_dias)."""
    return [dias_semana_es[d] for d in DIAS_CERRADOS]


def describir_horario_texto():
    """Genera una frase legible del horario, para inyectar en el prompt de la IA
    sin tener que escribir las horas a mano en varios sitios del texto."""
    partes = [f"{ini} a {fin}" for ini, fin in BLOQUES_HORARIO]
    if len(partes) == 1:
        return f"de {partes[0]}"
    return "de " + ", y de ".join(partes)