# app/__init__.py
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from pymongo import MongoClient
import sys
import os

# Agregar el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import Config
    print("✅ Configuración importada correctamente")
except ImportError as e:
    print(f"❌ Error importando config: {e}")
    raise

import bcrypt

# Inicializar extensiones
login_manager = LoginManager()
csrf = CSRFProtect()
mongo_client = None
db = None

def create_app(config_class=Config):
    global mongo_client, db
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configurar MongoDB
    try:
        mongo_client = MongoClient(app.config['MONGO_URI'])
        db = mongo_client[app.config['MONGO_DB']]
        
        # Probar conexión
        mongo_client.admin.command('ping')
        print(f"✅ Conectado a MongoDB: {app.config['MONGO_DB']}")
        
    except Exception as e:
        print(f"❌ Error conectando a MongoDB: {e}")
        print("   Asegúrate de que MongoDB esté corriendo")
        print("   ⚠️ Continuando sin MongoDB para mostrar la página de inicio")
    
    # Crear índices únicos (solo si MongoDB está conectado)
    if db is not None:
        try:
            # Usuarios
            try:
                db.users.create_index('correo', unique=True)
                print("✅ Índice 'correo' en usuarios")
            except Exception as e:
                if 'already exists' in str(e):
                    print("ℹ️ Índice 'correo' ya existe")
                else:
                    print(f"⚠️ Error en índice correo: {e}")
            
            # Materiales - Verificar si el índice ya existe
            try:
                # Verificar si el índice ya existe
                existing_indexes = [idx['name'] for idx in db.materiales.list_indexes()]
                
                if 'idx_clave_unique' in existing_indexes:
                    print("ℹ️ Índice 'idx_clave_unique' ya existe")
                else:
                    # Eliminar índice antiguo si existe
                    try:
                        db.materiales.drop_index('clave_material_1')
                        print("✅ Índice 'clave_material_1' eliminado")
                    except:
                        pass
                    
                    # Crear el índice correcto
                    db.materiales.create_index('clave', unique=True, name='idx_clave_unique')
                    print("✅ Índice 'idx_clave_unique' creado")
                    
            except Exception as e:
                print(f"⚠️ Error con índices de materiales: {e}")
            
            # Vehículos
            try:
                db.vehiculos.create_index('eco', unique=True)
                print("✅ Índice 'eco' en vehículos")
            except Exception as e:
                if 'already exists' in str(e):
                    print("ℹ️ Índice 'eco' ya existe")
                else:
                    print(f"⚠️ Error en índice eco: {e}")
                    
            print("✅ Proceso de índices completado")
            
        except Exception as e:
            print(f"⚠️ Error general creando índices: {e}")
    
    # Inicializar Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    
    # Inicializar CSRF
    csrf.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        if db is None:
            return None
        from app.models import Usuario
        from bson import ObjectId
        try:
            user_data = db.users.find_one({'_id': ObjectId(user_id)})
            if user_data:
                return Usuario(user_data)
        except:
            pass
        return None
    
    # Registrar blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    return app