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

def guardar_foto(file, nombre_base, foto_actual=None):
    """Función auxiliar para procesar y guardar la imagen de perfil"""
    if file and file.filename != '':
        # Aseguramos un nombre de archivo seguro y único
        ext = os.path.splitext(file.filename)[1]
        filename = secure_filename(f"{nombre_base.replace(' ', '_')}_{int(datetime.utcnow().timestamp())}{ext}")
        
        # Ruta: app/static/img/usuarios/
        upload_path = os.path.join(current_app.root_path, 'static', 'img', 'usuarios')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
            
        file.save(os.path.join(upload_path, filename))
        return filename
    return foto_actual if foto_actual else "default.png"

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirigir según el rol del usuario ya autenticado
        if current_user.is_admin:
            return redirect(url_for('main.dashboard'))
        else:
            return redirect(url_for('main.user_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user, error = Usuario.verificar_credenciales(db, form.correo.data, form.password.data)
        if user:
            login_user(user, remember=True)
            flash(f'¡Bienvenido {user.nombre}!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            # Redirigir según el rol del usuario
            if user.is_admin:
                return redirect(url_for('main.dashboard'))
            else:
                return redirect(url_for('main.user_dashboard'))
        else:
            flash(error, 'danger')
    return render_template('auth/login.html', form=form)

# RUTA GET PARA VISTA DE REGISTRO
@main_bp.route('/registro', methods=['GET'])
def registro_page():
    """Vista de registro de usuarios"""
    from app.forms import RegistroForm
    form = RegistroForm()
    return render_template('registro.html', form=form)

# RUTA POST PARA REGISTRO DE USUARIOS
@main_bp.route('/registro', methods=['POST'])
def registro():
    """Registro de nuevos usuarios desde la página de login"""
    try:
        nombre = request.form.get('nombre', '').strip()
        correo = request.form.get('correo', '').strip()
        password = request.form.get('password', '')
        foto = request.files.get('foto_usuario')
        
        # Validaciones
        if not nombre or not correo or not password:
            return jsonify({'message': 'Todos los campos son obligatorios'}), 400
        
        # Validar dominio de correo
        if not (correo.endswith('@bonafont.com') or correo.endswith('@danone.com')):
            return jsonify({'message': 'Solo se permiten correos con dominio @bonafont.com o @danone.com'}), 400
        
        # Validar contraseña
        if len(password) < 6 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            return jsonify({'message': 'La contraseña debe tener al menos 6 caracteres, una mayúscula y un número'}), 400
        
        # Verificar si el correo ya existe
        existing_user = db.users.find_one({'correo': correo})
        if existing_user:
            return jsonify({'message': 'El correo ya está registrado'}), 400
        
        # Guardar foto si se proporcionó
        nombre_foto = "default.png"
        if foto and foto.filename:
            nombre_foto = guardar_foto(foto, nombre)
        
        # Crear usuario usando bcrypt (coherente con el modelo)
        import bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        nuevo_usuario = {
            'nombre': nombre,
            'correo': correo,
            'password': hashed_password,
            'tipo_usuario': 2,  # Usuario normal por defecto
            'foto_usuario_url': nombre_foto,
            'fecha_registro': datetime.utcnow(),
            'activo': True,
            'intentos_fallidos': 0,
            'bloqueado_hasta': None
        }
        
        result = db.users.insert_one(nuevo_usuario)
        
        return jsonify({
            'success': True, 
            'message': 'Usuario registrado exitosamente',
            'user_id': str(result.inserted_id)
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Error al registrar: {str(e)}'}), 500

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

# --- RUTA PARA REPORTES ---

@main_bp.route('/reportes')
@login_required
def reportes():
    """Vista de reportes de fallas"""
    return render_template('auth/reportes.html')

# --- RUTAS CRUD PARA VEHÍCULOS ---

@main_bp.route('/vehiculos')
@login_required
def vehiculos():
    """Vista principal de gestión de vehículos"""
    vehiculos = list(db.vehiculos.find())
    lugares = list(db.lugares.find())
    return render_template('auth/vehiculos.html', vehiculos=vehiculos, lugares=lugares)

@main_bp.route('/vehiculos/add', methods=['POST'])
@login_required
def add_vehiculo():
    """Agregar un nuevo vehículo vía AJAX"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400

    eco = data.get('eco', '').strip()
    if db.vehiculos.find_one({'eco': eco}):
        return jsonify({'error': f'El ECO {eco} ya existe'}), 400

    nuevo_vehiculo = {
        'eco': eco,
        'placas': data.get('placas', '').strip(),
        'anio': data.get('anio'),
        'marca': data.get('marca', '').strip(),
        'modelo': data.get('modelo', '').strip(),
        'kilometraje': data.get('kilometraje', 0),
        'conductor': data.get('conductor', '').strip(),
        'estado': data.get('estado', 'Activo'),
        'lugar': data.get('lugar', ''),
        'fecha_registro': datetime.utcnow()
    }
    
    try:
        db.vehiculos.insert_one(nuevo_vehiculo)
        return jsonify({'message': 'Vehículo guardado correctamente'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/vehiculos/<id>', methods=['GET'])
@login_required
def get_vehiculo(id):
    """Obtener datos de un vehículo para el modal de edición/ver"""
    try:
        vehiculo = db.vehiculos.find_one({'_id': ObjectId(id)})
        if vehiculo:
            vehiculo['_id'] = str(vehiculo['_id'])
            return jsonify(vehiculo)
        return jsonify({'error': 'Vehículo no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/vehiculos/update/<id>', methods=['POST'])
@login_required
def update_vehiculo(id):
    """Actualizar datos de un vehículo"""
    data = request.get_json()
    try:
        updated_data = {
            'placas': data.get('placas', '').strip(),
            'anio': data.get('anio'),
            'marca': data.get('marca', '').strip(),
            'modelo': data.get('modelo', '').strip(),
            'kilometraje': data.get('kilometraje'),
            'conductor': data.get('conductor', '').strip(),
            'estado': data.get('estado'),
            'lugar': data.get('lugar')
        }
        db.vehiculos.update_one({'_id': ObjectId(id)}, {'$set': updated_data})
        return jsonify({'message': 'Vehículo actualizado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/vehiculos/delete/<id>', methods=['DELETE'])
@login_required
def delete_vehiculo(id):
    """Eliminar un vehículo"""
    try:
        db.vehiculos.delete_one({'_id': ObjectId(id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    
    # Validación más estricta de la clave
    if not clave:
        flash('La clave del material es obligatoria.', 'danger')
        return redirect(url_for('main.materiales'))
    
    # Verificar que la clave no sea solo espacios
    if len(clave) == 0:
        flash('La clave del material no puede estar vacía.', 'danger')
        return redirect(url_for('main.materiales'))
    
    descripcion = request.form.get('descripcion', '').strip()
    if not descripcion:
        flash('La descripción del material es obligatoria.', 'danger')
        return redirect(url_for('main.materiales'))
    
    # Verificar existencia de material con misma clave (case insensitive)
    existing_material = db.materiales.find_one({'clave': {'$regex': f'^{clave}$', '$options': 'i'}})
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
        'generico': request.form.get('generico', '').strip() or None,
        'clasificacion': request.form.get('clasificacion', '') or None,
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
        # Capturar error específico de duplicado
        if 'duplicate key' in str(e).lower():
            flash(f'Ya existe un material con la clave "{clave}".', 'danger')
        else:
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
    
    existing = db.materiales.find_one({
        'clave': {'$regex': f'^{clave}$', '$options': 'i'},
        '_id': {'$ne': ObjectId(id)}
    })
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
        'generico': request.form.get('generico', '').strip() or None,
        'clasificacion': request.form.get('clasificacion', '') or None,
        'existencia': existencia,
        'costo': costo,
        'lugar_id': request.form.get('lugar_id') if request.form.get('lugar_id') else None
    }
    
    try:
        result = db.materiales.update_one({'_id': ObjectId(id)}, {'$set': datos})
        if result.modified_count > 0:
            flash('Material actualizado correctamente', 'success')
        else:
            flash('No se realizaron cambios', 'info')
    except Exception as e:
        if 'duplicate key' in str(e).lower():
            flash(f'Ya existe un material con la clave "{clave}"', 'danger')
        else:
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

@main_bp.route('/user/update/<id>', methods=['POST'])
@login_required
def update_user(id):
    """Actualizar datos de un usuario"""
    nombre = request.form.get('nombre')
    correo = request.form.get('correo')
    password = request.form.get('password')
    tipo = int(request.form.get('tipo_usuario', 2))
    foto = request.files.get('foto_usuario')
    
    try:
        # Obtener usuario actual
        usuario_actual = db.users.find_one({'_id': ObjectId(id)})
        if not usuario_actual:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('main.dashboard'))
        
        # Verificar si el correo ya existe en otro usuario
        if correo != usuario_actual['correo']:
            existe = db.users.find_one({'correo': correo, '_id': {'$ne': ObjectId(id)}})
            if existe:
                flash('El correo ya está registrado por otro usuario', 'danger')
                return redirect(url_for('main.dashboard'))
        
        # Guardar nueva foto si se proporcionó
        nombre_foto = guardar_foto(foto, nombre, usuario_actual.get('foto_usuario_url'))
        
        # Preparar datos de actualización
        datos_actualizar = {
            'nombre': nombre,
            'correo': correo,
            'tipo_usuario': tipo,
            'foto_usuario_url': nombre_foto
        }
        
        # Actualizar contraseña solo si se proporcionó
        if password and password.strip():
            from werkzeug.security import generate_password_hash
            datos_actualizar['password'] = generate_password_hash(password)
        
        # Actualizar en la base de datos
        result = db.users.update_one(
            {'_id': ObjectId(id)},
            {'$set': datos_actualizar}
        )
        
        if result.modified_count > 0:
            flash('Usuario actualizado correctamente', 'success')
        else:
            flash('No se realizaron cambios', 'info')
            
    except Exception as e:
        flash(f'Error al actualizar usuario: {str(e)}', 'danger')
    
    return redirect(url_for('main.dashboard'))

@main_bp.route('/user/delete/<id>', methods=['DELETE'])
@login_required
def delete_user(id):
    if id == str(current_user.id):
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400
    Usuario.eliminar_usuario(db, id)
    return jsonify({'success': True})

# --- RUTAS CRUD PARA LUGARES ---

@main_bp.route('/lugares')
@login_required
def lugares():
    """Vista principal de gestión de lugares"""
    lugares = list(db.lugares.find())
    return render_template('auth/lugares.html', lugares=lugares)

@main_bp.route('/lugares/add', methods=['POST'])
@login_required
def add_lugar():
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
    try:
        db.lugares.delete_one({'_id': ObjectId(id)})
        return jsonify({'message': 'Lugar eliminado correctamente'}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    
# ================================================
# RUTAS PARA USUARIOS NORMALES (con vistas separadas)
# ================================================

# Ruta para buscar vehículos (usada en reportes)
@main_bp.route('/buscar-vehiculos', methods=['GET'])
@login_required
def buscar_vehiculos():
    """Buscar vehículos por número económico o placas (AJAX)"""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])
    
    # Buscar vehículos que coincidan con la búsqueda
    vehiculos = list(db.vehiculos.find({
        '$or': [
            {'eco': {'$regex': q, '$options': 'i'}},
            {'placas': {'$regex': q, '$options': 'i'}}
        ]
    }).limit(10))
    
    resultados = []
    for v in vehiculos:
        resultados.append({
            'id': str(v['_id']),
            'economico': v.get('eco', ''),
            'placas': v.get('placas', ''),
            'marca': v.get('marca', ''),
            'modelo': v.get('modelo', '')
        })
    
    return jsonify(resultados)


# Dashboard del usuario normal
@main_bp.route('/user/dashboard')
@login_required
def user_dashboard():
    """Vista principal para usuarios normales"""
    from datetime import datetime, timedelta
    
    # Obtener vehículos asignados al usuario
    vehiculos_asignados = list(db.vehiculos.find({'conductor': current_user.nombre}))
    
    # Obtener historial de materiales utilizados por el usuario
    historial = list(db.historial_uso.find({'usuario_id': ObjectId(current_user.id)}).sort('fecha', -1).limit(10))
    
    # Enriquecer historial con descripciones de materiales
    for h in historial:
        material = db.materiales.find_one({'_id': h['material_id']})
        if material:
            h['material_descripcion'] = material.get('descripcion', '')
        else:
            h['material_descripcion'] = 'Material no disponible'
        
        # Obtener información del vehículo
        if h.get('vehiculo_id'):
            vehiculo = db.vehiculos.find_one({'_id': h['vehiculo_id']})
            if vehiculo:
                h['vehiculo_info'] = f"{vehiculo.get('eco', '')} - {vehiculo.get('placas', '')}"
            else:
                h['vehiculo_info'] = 'No especificado'
        else:
            h['vehiculo_info'] = 'No especificado'
    
    # Materiales con stock bajo (menos de 10 unidades)
    stock_bajo = list(db.materiales.find({'existencia': {'$lt': 10}}).limit(5))
    for m in stock_bajo:
        if m.get('lugar_id'):
            lugar = db.lugares.find_one({'_id': ObjectId(m['lugar_id'])})
            m['lugar_nombre'] = lugar.get('nombre', '-') if lugar else '-'
        else:
            m['lugar_nombre'] = '-'
    
    # Estadísticas
    stats = {
        'vehiculos_asignados': len(vehiculos_asignados),
        'materiales_utilizados': db.historial_uso.count_documents({'usuario_id': ObjectId(current_user.id)}),
        'total_reportes': db.historial_uso.count_documents({'usuario_id': ObjectId(current_user.id)}),
        'stock_bajo': len(stock_bajo)
    }
    
    return render_template('auth/user_dashboard.html', 
                         vehiculos_asignados=vehiculos_asignados,
                         historial=historial,
                         stock_bajo=stock_bajo,
                         stats=stats)


# Vista de vehículos para usuario normal (solo lectura)
@main_bp.route('/user/vehiculos')
@login_required
def user_vehiculos():
    """Vista de vehículos para usuarios normales (solo los asignados)"""
    vehiculos = list(db.vehiculos.find({'conductor': current_user.nombre}))
    return render_template('auth/user_vehiculos.html', vehiculos=vehiculos)


# Vista de materiales para usuario normal
@main_bp.route('/user/materiales')
@login_required
def user_materiales():
    """Vista de materiales para usuarios normales (solo lectura y reporte)"""
    materiales = list(db.materiales.find())
    
    # Enriquecer con nombre del lugar
    for m in materiales:
        if m.get('lugar_id'):
            lugar = db.lugares.find_one({'_id': ObjectId(m['lugar_id'])})
            m['lugar_nombre'] = lugar.get('nombre', '-') if lugar else '-'
        else:
            m['lugar_nombre'] = '-'
    
    return render_template('auth/user_materiales.html', materiales=materiales)


# Vista de reportes para usuario normal (solo sus reportes)
@main_bp.route('/user/reportes')
@login_required
def user_reportes():
    """Vista de reportes para usuarios normales (solo sus reportes)"""
    reportes = list(db.historial_uso.find({'usuario_id': ObjectId(current_user.id)}).sort('fecha', -1))
    
    # Enriquecer reportes con información adicional
    total_costo = 0
    materiales_set = set()
    
    for r in reportes:
        # Formatear fecha
        if isinstance(r.get('fecha'), datetime):
            r['fecha'] = r['fecha']
        else:
            r['fecha'] = datetime.utcnow()
        
        # Obtener descripción del material
        material = db.materiales.find_one({'_id': r['material_id']})
        if material:
            r['material_descripcion'] = material.get('descripcion', '')
            r['costo_unitario'] = material.get('costo', 0)
            materiales_set.add(r['material_clave'])
        else:
            r['material_descripcion'] = 'Material no disponible'
            r['costo_unitario'] = 0
        
        # Calcular costo total
        r['costo_total'] = r.get('costo_total', r['cantidad'] * r['costo_unitario'])
        total_costo += r['costo_total']
        
        # Obtener información del vehículo
        if r.get('vehiculo_id'):
            vehiculo = db.vehiculos.find_one({'_id': r['vehiculo_id']})
            if vehiculo:
                r['vehiculo_info'] = f"{vehiculo.get('eco', '')} - {vehiculo.get('placas', '')}"
            else:
                r['vehiculo_info'] = 'No especificado'
        else:
            r['vehiculo_info'] = 'No especificado'
    
    stats = {
        'total_reportes': len(reportes),
        'total_materiales': len(materiales_set),
        'costo_total': total_costo
    }
    
    return render_template('auth/user_reportes.html', reportes=reportes, stats=stats)


# Vista de perfil para usuario normal
@main_bp.route('/user/perfil')
@login_required
def user_perfil():
    """Vista de perfil para usuarios normales"""
    return render_template('auth/user_perfil.html')


# Actualizar perfil de usuario normal (SOLO nombre y foto)
@main_bp.route('/user/update-perfil', methods=['POST'])
@login_required
def user_update_perfil():
    """Actualizar información del perfil del usuario normal (solo nombre y foto)"""
    nombre = request.form.get('nombre', '').strip()
    foto = request.files.get('foto_usuario')
    
    try:
        # Validar que el nombre no esté vacío
        if not nombre:
            flash('El nombre no puede estar vacío', 'danger')
            return redirect(url_for('main.user_perfil'))
        
        # Obtener usuario actual
        usuario_actual = db.users.find_one({'_id': ObjectId(current_user.id)})
        if not usuario_actual:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('main.user_perfil'))
        
        # Guardar nueva foto si se proporcionó
        nombre_foto = usuario_actual.get('foto_usuario_url', 'default.png')
        if foto and foto.filename:
            nombre_foto = guardar_foto(foto, nombre, nombre_foto)
        
        # Preparar datos de actualización (SOLO nombre y foto)
        datos_actualizar = {
            'nombre': nombre,
            'foto_usuario_url': nombre_foto
        }
        
        # Actualizar en la base de datos
        result = db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': datos_actualizar}
        )
        
        if result.modified_count > 0:
            flash('Perfil actualizado correctamente', 'success')
        else:
            flash('No se realizaron cambios', 'info')
            
    except Exception as e:
        flash(f'Error al actualizar perfil: {str(e)}', 'danger')
    
    return redirect(url_for('main.user_perfil'))

# Detalle de reporte (AJAX)
@main_bp.route('/reporte-detalle/<reporte_id>', methods=['GET'])
@login_required
def reporte_detalle(reporte_id):
    """Obtener detalles de un reporte específico (AJAX)"""
    try:
        reporte = db.historial_uso.find_one({'_id': ObjectId(reporte_id)})
        
        # Verificar que el reporte pertenezca al usuario actual (seguridad)
        if str(reporte['usuario_id']) != str(current_user.id) and not current_user.is_admin:
            return jsonify({'error': 'No tienes permisos para ver este reporte'}), 403
        
        if reporte:
            # Obtener descripción del material
            material = db.materiales.find_one({'_id': reporte['material_id']})
            material_descripcion = material.get('descripcion', '') if material else 'Material no disponible'
            costo_unitario = material.get('costo', 0) if material else 0
            
            # Obtener información del vehículo
            vehiculo_info = 'No especificado'
            if reporte.get('vehiculo_id'):
                vehiculo = db.vehiculos.find_one({'_id': reporte['vehiculo_id']})
                if vehiculo:
                    vehiculo_info = f"{vehiculo.get('eco', '')} - {vehiculo.get('placas', '')}"
            
            return jsonify({
                '_id': str(reporte['_id']),
                'fecha': reporte['fecha'].strftime('%d/%m/%Y %H:%M') if isinstance(reporte['fecha'], datetime) else str(reporte['fecha']),
                'material_clave': reporte.get('material_clave', ''),
                'material_descripcion': material_descripcion,
                'cantidad': reporte.get('cantidad', 0),
                'costo_unitario': f"{costo_unitario:.2f}",
                'costo_total': f"{reporte.get('costo_total', 0):.2f}",
                'vehiculo_info': vehiculo_info
            })
        return jsonify({'error': 'Reporte no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
    # --- RUTAS PARA BACKUPS ---

from app.backup_utils import BackupManager
import platform

@main_bp.route('/backups')
@login_required
def backups():
    """Vista principal de gestión de backups"""
    from datetime import datetime as dt
    import os
    
    backup_manager = BackupManager(db)
    
    # Obtener estadísticas
    stats = backup_manager.get_backup_stats()
    
    # Obtener lista de backups (últimos 50)
    backups_list = list(db.backups.find().sort('backup_date', -1).limit(50))
    
    # Fecha actual para comparar expiración
    now = dt.now()
    
    # Formatear backups para la vista
    formatted_backups = []
    for backup in backups_list:
        # Crear una copia para no modificar el original
        formatted = dict(backup)
        
        formatted['_id'] = str(backup['_id'])
        
        # Formatear fecha de backup
        if isinstance(backup.get('backup_date'), datetime):
            formatted['backup_date'] = backup['backup_date'].strftime('%d/%m/%Y %H:%M')
            backup_date_obj = backup['backup_date']
        else:
            formatted['backup_date'] = str(backup.get('backup_date', 'N/A'))
            backup_date_obj = None
        
        # Formatear fecha de expiración y determinar si está expirado
        if isinstance(backup.get('expires_at'), datetime):
            formatted['expires_at'] = backup['expires_at'].strftime('%d/%m/%Y %H:%M')
            formatted['is_expired'] = backup['expires_at'] < now
        else:
            formatted['expires_at'] = 'No expira'
            formatted['is_expired'] = False
        
        formatted['formatted_type'] = {
            'complete': 'Completo',
            'differential': 'Diferencial',
            'incremental': 'Incremental'
        }.get(backup.get('type', ''), backup.get('type', ''))
        
        formatted['formatted_size'] = backup.get('size_formatted', '0 B')
        formatted['file_exists'] = os.path.exists(backup.get('file_path', '')) if backup.get('file_path') else False
        formatted['status'] = backup.get('status', 'unknown')
        formatted['type'] = backup.get('type', 'unknown')
        
        formatted_backups.append(formatted)
    
    # Agregar estadísticas de disco
    disk_usage = backup_manager.get_disk_usage()
    stats.update(disk_usage)
    
    return render_template('auth/backups.html', backups=formatted_backups, stats=stats, now=now)

@main_bp.route('/backups/stats', methods=['GET'])
@login_required
def backups_stats():
    """API: Obtener estadísticas de backups"""
    backup_manager = BackupManager(db)
    stats = backup_manager.get_backup_stats()
    disk_usage = backup_manager.get_disk_usage()
    stats.update(disk_usage)
    return jsonify({'success': True, 'stats': stats})

@main_bp.route('/backups/last-runs', methods=['GET'])
@login_required
def backups_last_runs():
    """API: Obtener últimas ejecuciones de backups"""
    last_backups = list(db.backups.find().sort('backup_date', -1).limit(3))
    last_complete = None
    last_differential = None
    last_incremental = None
    
    for backup in last_backups:
        if backup.get('type') == 'complete' and not last_complete:
            last_complete = backup['backup_date'].strftime('%d/%m/%Y %H:%M') if isinstance(backup['backup_date'], datetime) else str(backup['backup_date'])
        elif backup.get('type') == 'differential' and not last_differential:
            last_differential = backup['backup_date'].strftime('%d/%m/%Y %H:%M') if isinstance(backup['backup_date'], datetime) else str(backup['backup_date'])
        elif backup.get('type') == 'incremental' and not last_incremental:
            last_incremental = backup['backup_date'].strftime('%d/%m/%Y %H:%M') if isinstance(backup['backup_date'], datetime) else str(backup['backup_date'])
    
    return jsonify({
        'success': True,
        'last_complete': last_complete,
        'last_differential': last_differential,
        'last_incremental': last_incremental,
        'last_cleanup': 'Diario 01:00'
    })

@main_bp.route('/backups/create', methods=['POST'])
@login_required
def backups_create():
    """Crear un nuevo backup"""
    data = request.get_json()
    backup_type = data.get('type', 'complete')
    filename = data.get('filename', '')
    compress = data.get('compress', True)
    
    backup_manager = BackupManager(db)
    success, result = backup_manager.create_backup(backup_type, filename, compress)
    
    if success:
        return jsonify({'success': True, 'message': 'Backup creado exitosamente', 'backup': result})
    else:
        return jsonify({'success': False, 'message': result}), 500

@main_bp.route('/backups/<backup_id>', methods=['GET'])
@login_required
def backups_get(backup_id):
    """Obtener detalles de un backup"""
    try:
        backup = db.backups.find_one({'_id': ObjectId(backup_id)})
        if backup:
            backup['_id'] = str(backup['_id'])
            if isinstance(backup.get('backup_date'), datetime):
                backup['backup_date'] = backup['backup_date'].strftime('%d/%m/%Y %H:%M')
            if isinstance(backup.get('expires_at'), datetime):
                backup['expires_at'] = backup['expires_at'].strftime('%d/%m/%Y %H:%M')
            backup['size'] = backup.get('size_formatted', '0 B')
            backup['file_exists'] = os.path.exists(backup.get('file_path', '')) if backup.get('file_path') else False
            return jsonify({'success': True, 'backup': backup})
        return jsonify({'success': False, 'message': 'Backup no encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/backups/download/<backup_id>', methods=['GET'])
@login_required
def backups_download(backup_id):
    """Descargar archivo de backup"""
    try:
        backup = db.backups.find_one({'_id': ObjectId(backup_id)})
        if backup and os.path.exists(backup.get('file_path', '')):
            from flask import send_file
            return send_file(
                backup['file_path'],
                as_attachment=True,
                download_name=backup['filename'],
                mimetype='application/gzip'
            )
        return jsonify({'success': False, 'message': 'Archivo no encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/backups/<backup_id>', methods=['DELETE'])
@login_required
def backups_delete(backup_id):
    """Eliminar un backup"""
    backup_manager = BackupManager(db)
    success, message = backup_manager.delete_backup(backup_id)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'message': message}), 500

@main_bp.route('/backups/cleanup-expired', methods=['POST'])
@login_required
def backups_cleanup_expired():
    """Limpiar backups expirados"""
    backup_manager = BackupManager(db)
    success, message = backup_manager.cleanup_expired()
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'message': message}), 500

@main_bp.route('/backups/usb-devices', methods=['GET'])
@login_required
def backups_usb_devices():
    """Detectar dispositivos USB"""
    backup_manager = BackupManager(db)
    if platform.system() == 'Windows':
        drives = backup_manager.get_usb_drives_windows()
    else:
        # Para Linux/Mac se puede implementar similar
        drives = []
    return jsonify({'success': True, 'usb_drives': drives})

@main_bp.route('/backups/create-usb', methods=['POST'])
@login_required
def backups_create_usb():
    """Crear backup directamente en USB"""
    data = request.get_json()
    drive_letter = data.get('drive_letter')
    backup_type = data.get('type', 'complete')
    
    if not drive_letter:
        return jsonify({'success': False, 'message': 'Selecciona un dispositivo USB'}), 400
    
    backup_manager = BackupManager(db)
    success, message = backup_manager.create_usb_backup(drive_letter, backup_type)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'message': message}), 500

@main_bp.route('/backups/sync-to-usb', methods=['POST'])
@login_required
def backups_sync_to_usb():
    """Sincronizar backup existente a USB"""
    data = request.get_json()
    drive_letter = data.get('drive_letter')
    backup_id = data.get('backup_id')
    
    if not drive_letter or not backup_id:
        return jsonify({'success': False, 'message': 'Datos incompletos'}), 400
    
    backup_manager = BackupManager(db)
    success, message = backup_manager.sync_to_usb(drive_letter, backup_id)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'message': message}), 500

@main_bp.route('/backups/usb-files/<drive_letter>', methods=['GET'])
@login_required
def backups_usb_files(drive_letter):
    """Listar archivos de backup en USB"""
    backup_manager = BackupManager(db)
    files = backup_manager.get_usb_files(drive_letter)
    return jsonify({'success': True, 'files': files})

@main_bp.route('/backups/import-from-usb', methods=['POST'])
@login_required
def backups_import_from_usb():
    """Importar backup desde USB"""
    data = request.get_json()
    drive_letter = data.get('drive_letter')
    filename = data.get('filename')
    
    if not drive_letter or not filename:
        return jsonify({'success': False, 'message': 'Datos incompletos'}), 400
    
    backup_manager = BackupManager(db)
    success, message = backup_manager.import_from_usb(drive_letter, filename)
    
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'message': message}), 500

@main_bp.route('/backups/open-folder', methods=['POST'])
@login_required
def backups_open_folder():
    """Abrir carpeta de backups en explorador"""
    try:
        backup_manager = BackupManager(db)
        backup_path = backup_manager.backup_dir
        
        if platform.system() == 'Windows':
            os.startfile(backup_path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', backup_path])
        else:  # Linux
            subprocess.run(['xdg-open', backup_path])
        
        return jsonify({'success': True, 'message': 'Carpeta de backups abierta'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500