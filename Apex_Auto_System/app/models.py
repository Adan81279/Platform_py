# app/models.py
from flask_login import UserMixin
from bson import ObjectId
from datetime import datetime
import bcrypt

class Usuario(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.nombre = user_data.get('nombre', '')
        self.correo = user_data.get('correo', '')
        self.tipo_usuario = user_data.get('tipo_usuario', 2)
        self.activo = user_data.get('activo', True)
        self.foto_usuario_url = user_data.get('foto_usuario_url') or 'default.png'

    @property
    def is_admin(self):
        return self.tipo_usuario == 1

    @staticmethod
    def get_by_id(db, user_id):
        try:
            user_data = db.users.find_one({'_id': ObjectId(user_id)})
            return Usuario(user_data) if user_data else None
        except:
            return None

    @staticmethod
    def crear_usuario(db, nombre, correo, password, tipo_usuario=2, foto=None):
        if db.users.find_one({'correo': correo}):
            return None, "El correo ya está registrado"
        
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        user_data = {
            'nombre': nombre,
            'correo': correo,
            'password': hashed,
            'tipo_usuario': int(tipo_usuario),
            'fecha_creacion': datetime.utcnow(),
            'activo': True,
            'intentos_fallidos': 0,
            'bloqueado_hasta': None,
            'foto_usuario_url': foto if foto else 'default.png'
        }
        
        result = db.users.insert_one(user_data)
        return result.inserted_id, "Usuario creado exitosamente"

    @staticmethod
    def actualizar_usuario(db, user_id, datos):
        if 'password' in datos and datos['password']:
            datos['password'] = bcrypt.hashpw(datos['password'].encode('utf-8'), bcrypt.gensalt())
        else:
            datos.pop('password', None)

        db.users.update_one({'_id': ObjectId(user_id)}, {'$set': datos})
        return True

    @staticmethod
    def eliminar_usuario(db, user_id):
        db.users.delete_one({'_id': ObjectId(user_id)})
        return True

    @staticmethod
    def verificar_credenciales(db, correo, password):
        user = db.users.find_one({'correo': correo, 'activo': True})
        
        if not user:
            return None, "Usuario no encontrado"
        
        if user.get('bloqueado_hasta') and user['bloqueado_hasta'] > datetime.utcnow():
            return None, "Usuario bloqueado. Intente más tarde"
        
        try:
            if bcrypt.checkpw(password.encode('utf-8'), user['password']):
                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'intentos_fallidos': 0, 'bloqueado_hasta': None}}
                )
                return Usuario(user), None
            else:
                intentos = user.get('intentos_fallidos', 0) + 1
                update_data = {'intentos_fallidos': intentos}
                
                if intentos >= 5:
                    from datetime import timedelta
                    update_data['bloqueado_hasta'] = datetime.utcnow() + timedelta(minutes=30)
                
                db.users.update_one({'_id': user['_id']}, {'$set': update_data})
                return None, "Contraseña incorrecta"
        except Exception as e:
            return None, f"Error de autenticación: {str(e)}"