import os
from flask import Flask
from routes.web import web_blueprint
from routes.webhook import webhook_blueprint
from dotenv import load_dotenv

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY', 'clave_por_defecto_segura')

# Registrar las rutas en la app
app.register_blueprint(web_blueprint)
app.register_blueprint(webhook_blueprint)

# Arrancador del server
if __name__ == "__main__":
    app.run(debug=True)

    