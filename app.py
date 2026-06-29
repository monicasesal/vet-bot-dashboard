from flask import Flask, render_template

# Inicializar Flask
app = Flask(__name__)

# Ruta principal
@app.route("/")
def inicio():
    citas_veterinaria = [
        {"hora": "10:00", "paciente": "Toby 🐶", "motivo": "Vacuna"},
        {"hora": "11:30", "paciente": "Luna 🐱", "motivo": "Revisión"},
        {"hora": "16:00", "paciente": "Thor 🐹", "motivo": "Corte de uñas"}
    ]

    chats_activos = [
        {"usuario": "Carlos (Dueño de Rocky)", "mensaje": "Mi perro no quiere comer hoy", "atendido_por": "IA"},
        {"usuario": "María (Dueña de Michi)", "mensaje": "¡Es una emergencia! Se ha tragado un hilo", "atendido_por": "Humano"},
        {"usuario": "Ana (Dueña de Piolín)", "mensaje": "Muchas gracias por la cita", "atendido_por": "IA"}
    ]
    return render_template("index.html", mis_citas=citas_veterinaria, los_chats=chats_activos)

# Arrancador del server
if __name__ == "__main__":
    app.run(debug=True)