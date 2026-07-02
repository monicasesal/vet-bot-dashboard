from flask import Flask, render_template, request, redirect
from routes.web import web_blueprint

app = Flask(__name__)

# Registrar las rutas en la app
app.register_blueprint(web_blueprint)

# Arrancador del server
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)