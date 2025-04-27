from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import os
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/comprobantes'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
app.secret_key = 'supersecretkey'  # Necesario para los flashes

# MongoDB Atlas connection
client = MongoClient(os.getenv('MONGO_URI'))
db = client['hotel_dashboard']
habitaciones_collection = db['habitaciones']

# Flask-SocketIO para tiempo real
socketio = SocketIO(app, cors_allowed_origins="*")

# Diccionario para cooldown por habitación
cooldowns = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def dashboard():
    habitaciones = list(habitaciones_collection.find())
    return render_template('dashboard.html', habitaciones=habitaciones)

@app.route('/habitacion/<habitacion_id>', methods=['GET', 'POST'])
def habitacion(habitacion_id):
    habitacion = habitaciones_collection.find_one({"_id": habitacion_id})

    if request.method == 'POST':
        # Verificar cooldown
        last_update = cooldowns.get(habitacion_id, 0)
        if time.time() - last_update < 15:
            flash('Debes esperar 15 segundos antes de modificar esta habitación.')
            return redirect(url_for('habitacion', habitacion_id=habitacion_id))

        estado = request.form['estado']
        update_data = {"estado": estado}

        if estado == "Reservada":
            nombre = request.form['nombre']
            celular = request.form['celular']
            fecha_llegada = request.form['fecha_llegada']
            hora_llegada = request.form['hora_llegada']
            personas = request.form['personas']
            update_data.update({
                "nombre": nombre,
                "celular": celular,
                "fecha_llegada": fecha_llegada,
                "hora_llegada": hora_llegada,
                "personas": personas
            })

            # Subida de imagen comprobante
            if 'comprobante' in request.files:
                file = request.files['comprobante']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    update_data['comprobante'] = filepath

        habitaciones_collection.update_one({"_id": habitacion_id}, {"$set": update_data})
        cooldowns[habitacion_id] = time.time()

        # Emitir el cambio en tiempo real
        socketio.emit('habitacion_actualizada', {'habitacion_id': habitacion_id, 'estado': estado})
        flash('Habitación actualizada exitosamente.')
        return redirect(url_for('dashboard'))

    return render_template('habitacion.html', habitacion=habitacion)

@socketio.on('connect')
def on_connect():
    print('Cliente conectado.')

if __name__ == '__main__':
    socketio.run(app, debug=True)
