# app/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import Usuario
from app.forms import LoginForm, RegistroForm
from bson import ObjectId
import os
from werkzeug.utils import secure_filename
from datetime import datetime

main_bp = Blueprint('main', __name__, template_folder='templates')

def guardar_foto(file, nombre_base):
    """Función auxiliar para procesar y guardar la imagen de perfil"""
    if file and file.filename != '':
        # Aseguramos un nombre de archivo seguro y único
        ext = os.path.splitext(file.filename)[1]
        filename = secure_filename(f"{nombre_base.replace(' ', '_')}_{int(datetime.utcnow().timestamp())}{ext}")
        
        # Ruta: app/static/img/usuarios/
        upload_path = os.path.join('app', 'static', 'img', 'usuarios')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
            
        file.save(os.path.join(upload_path, filename))
        return filename
    return "default.png"

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user, error = Usuario.verificar_credenciales(db, form.correo.data, form.password.data)
        if user:
            login_user(user, remember=True)
            flash(f'¡Bienvenido {user.nombre}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash(error, 'danger')
    return render_template('auth/login.html', form=form)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    usuarios = list(db.users.find())
    lugares = list(db.lugares.find())
    return render_template('auth/dashboard.html', usuarios=usuarios, lugares=lugares)

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('main.index'))

# --- RUTAS CRUD PARA MATERIALES ---

@main_bp.route('/materiales')
@login_required
def materiales():
    """Vista de inventario de materiales"""
    materiales = list(db.materiales.find())
    lugares = list(db.lugares.find())
    return render_template('auth/materiales.html', materiales=materiales, lugares=lugares)

@main_bp.route('/material/add', methods=['POST'])
@login_required
def add_material():
    """Agregar nuevo material con todos los campos"""
    clave = request.form.get('clave', '').strip()
    if not clave:
        flash('La clave del material es obligatoria.', 'danger')
        return redirect(url_for('main.materiales'))
    
    descripcion = request.form.get('descripcion', '').strip()
    if not descripcion:
        flash('La descripción del material es obligatoria.', 'danger')
        return redirect(url_for('main.materiales'))
    
    existing_material = db.materiales.find_one({'clave': clave})
    if existing_material:
        flash(f'Ya existe un material con la clave "{clave}".', 'danger')
        return redirect(url_for('main.materiales'))
    
    try:
        existencia = int(request.form.get('existencia', 0))
        if existencia < 0: existencia = 0
    except ValueError:
        existencia = 0
    
    try:
        costo = float(request.form.get('costo', 0))
        if costo < 0: costo = 0
    except ValueError:
        costo = 0
    
    material = {
        'clave': clave,
        'descripcion': descripcion,
        'generico': request.form.get('generico', '').strip(),
        'clasificacion': request.form.get('clasificacion', ''),
        'existencia': existencia,
        'costo': costo,
        'lugar_id': request.form.get('lugar_id') if request.form.get('lugar_id') else None,
        'fecha_creacion': datetime.utcnow(),
        'creado_por': current_user.id
    }
    
    try:
        db.materiales.insert_one(material)
        flash(f'Material "{clave}" agregado exitosamente', 'success')
    except Exception as e:
        flash(f'Error al guardar el material: {str(e)}', 'danger')
    
    return redirect(url_for('main.materiales'))

@main_bp.route('/material/<id>', methods=['GET'])
@login_required
def get_material(id):
    try:
        material = db.materiales.find_one({'_id': ObjectId(id)})
        if material:
            lugar = None
            if material.get('lugar_id'):
                try:
                    lugar_data = db.lugares.find_one({'_id': ObjectId(material['lugar_id'])})
                    lugar = lugar_data.get('nombre') if lugar_data else ''
                except:
                    lugar = ''
            
            return jsonify({
                'id': str(material['_id']),
                'clave': material.get('clave', ''),
                'descripcion': material.get('descripcion', ''),
                'generico': material.get('generico', ''),
                'clasificacion': material.get('clasificacion', ''),
                'existencia': material.get('existencia', 0),
                'costo': material.get('costo', 0),
                'lugar_id': material.get('lugar_id', ''),
                'lugar_nombre': lugar
            })
        return jsonify({'error': 'Material no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/material/update/<id>', methods=['POST'])
@login_required
def update_material(id):
    clave = request.form.get('clave', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    
    if not clave or not descripcion:
        flash('Clave y descripción son obligatorias', 'danger')
        return redirect(url_for('main.materiales'))
    
    existing = db.materiales.find_one({'clave': clave, '_id': {'$ne': ObjectId(id)}})
    if existing:
        flash(f'Ya existe otro material con la clave "{clave}"', 'danger')
        return redirect(url_for('main.materiales'))
    
    try:
        existencia = int(request.form.get('existencia', 0))
        costo = float(request.form.get('costo', 0))
    except ValueError:
        existencia = 0
        costo = 0
    
    datos = {
        'clave': clave,
        'descripcion': descripcion,
        'generico': request.form.get('generico', '').strip(),
        'clasificacion': request.form.get('clasificacion', ''),
        'existencia': existencia,
        'costo': costo,
        'lugar_id': request.form.get('lugar_id') if request.form.get('lugar_id') else None
    }
    
    try:
        db.materiales.update_one({'_id': ObjectId(id)}, {'$set': datos})
        flash('Material actualizado correctamente', 'success')
    except Exception as e:
        flash(f'Error al actualizar: {str(e)}', 'danger')
    
    return redirect(url_for('main.materiales'))

@main_bp.route('/material/delete/<id>', methods=['DELETE'])
@login_required
def delete_material(id):
    try:
        db.materiales.delete_one({'_id': ObjectId(id)})
        return jsonify({'success': True, 'message': 'Material eliminado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/material/reportar', methods=['POST'])
@login_required
def reportar_uso():
    material_id = request.form.get('material_id')
    cantidad = int(request.form.get('cantidad', 1))
    vehiculo_id = request.form.get('vehiculo_id')
    
    material = db.materiales.find_one({'_id': ObjectId(material_id)})
    if not material or material['existencia'] < cantidad:
        return jsonify({'error': 'Existencia insuficiente'}), 400
    
    nueva_existencia = material['existencia'] - cantidad
    db.materiales.update_one({'_id': ObjectId(material_id)}, {'$set': {'existencia': nueva_existencia}})
    
    historial = {
        'material_id': ObjectId(material_id),
        'material_clave': material['clave'],
        'cantidad': cantidad,
        'vehiculo_id': ObjectId(vehiculo_id) if vehiculo_id else None,
        'usuario_id': ObjectId(current_user.id),
        'fecha': datetime.utcnow(),
        'costo_total': material.get('costo', 0) * cantidad
    }
    db.historial_uso.insert_one(historial)
    return jsonify({'success': True})

# --- RUTAS CRUD PARA USUARIOS ---

@main_bp.route('/user/add', methods=['POST'])
@login_required
def add_user():
    nombre = request.form.get('nombre')
    correo = request.form.get('correo')
    password = request.form.get('password')
    tipo = int(request.form.get('tipo_usuario', 2))
    foto = request.files.get('foto_usuario')
    nombre_foto = guardar_foto(foto, nombre)
    
    result, message = Usuario.crear_usuario(db, nombre, correo, password, tipo, foto=nombre_foto)
    flash("Usuario creado con éxito" if result else message, "success" if result else "danger")
    return redirect(url_for('main.dashboard'))

@main_bp.route('/user/<id>', methods=['GET'])
@login_required
def get_user(id):
    try:
        user_data = db.users.find_one({'_id': ObjectId(id)})
        if user_data:
            return jsonify({
                'id': str(user_data['_id']),
                'nombre': user_data['nombre'],
                'correo': user_data['correo'],
                'tipo_usuario': user_data.get('tipo_usuario', 2),
                'foto_usuario_url': user_data.get('foto_usuario_url', 'default.png')
            })
        return jsonify({'error': 'No encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/user/delete/<id>', methods=['DELETE'])
@login_required
def delete_user(id):
    if id == str(current_user.id):
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400
    Usuario.eliminar_usuario(db, id)
    return jsonify({'success': True})

# --- RUTAS CRUD PARA LUGARES (JSON ESTRICTO) ---

@main_bp.route('/lugares')
@login_required
def lugares():
    """Vista principal de gestión de lugares"""
    lugares = list(db.lugares.find())
    return render_template('auth/lugares.html', lugares=lugares)

@main_bp.route('/lugares/add', methods=['POST'])
@login_required
def add_lugar():
    # Priorizamos JSON, luego Form
    data = request.get_json(silent=True) or request.form
    
    if not data:
        return jsonify({'message': 'No se recibieron datos (Vacío)'}), 400

    nombre = data.get('nombre', '').strip()
    estado = data.get('estado', '').strip()
    
    if not nombre:
        return jsonify({'message': 'El nombre es obligatorio'}), 400

    try:
        db.lugares.insert_one({
            'nombre': nombre, 
            'estado': estado,
            'fecha_creacion': datetime.utcnow()
        })
        return jsonify({'message': 'Lugar registrado exitosamente'}), 201
    except Exception as e:
        return jsonify({'message': f'Error en DB: {str(e)}'}), 500

@main_bp.route('/lugares/<id>', methods=['GET'])
@login_required
def get_lugar(id):
    """Obtener datos de un lugar"""
    try:
        lugar = db.lugares.find_one({'_id': ObjectId(id)})
        if lugar:
            return jsonify({
                '_id': str(lugar['_id']),
                'nombre': lugar.get('nombre', ''),
                'estado': lugar.get('estado', '')
            })
        return jsonify({'message': 'Lugar no encontrado'}), 404
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@main_bp.route('/lugares/update/<id>', methods=['POST'])
@login_required
def update_lugar(id):
    data = request.get_json(silent=True) or request.form
    
    if not data:
        return jsonify({'message': 'No se recibieron datos para actualizar'}), 400

    nombre = data.get('nombre', '').strip()
    estado = data.get('estado', '').strip()

    if not nombre:
        return jsonify({'message': 'El nombre es obligatorio'}), 400

    try:
        # Importante: Asegurar que el id sea un ObjectId válido
        result = db.lugares.update_one(
            {'_id': ObjectId(id)},
            {'$set': {'nombre': nombre, 'estado': estado}}
        )
        
        if result.matched_count == 0:
            return jsonify({'message': 'Lugar no encontrado'}), 404
            
        return jsonify({'message': 'Actualizado correctamente'}), 200
    except Exception as e:
        return jsonify({'message': f'Error: {str(e)}'}), 500

@main_bp.route('/lugares/<id>', methods=['DELETE'])
@login_required
def delete_lugar(id):
    """Eliminar un lugar"""
    try:
        db.lugares.delete_one({'_id': ObjectId(id)})
        return jsonify({'message': 'Lugar eliminado correctamente'}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500