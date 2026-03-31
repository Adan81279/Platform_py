import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'apex-auto-secret-key-2025'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/'
    MONGO_DB = os.environ.get('MONGO_DB') or 'apex_auto_db'
    UPLOAD_FOLDER = os.path.join('app', 'static', 'img', 'usuarios')
    
    # Configuración de sesión
    SESSION_TIMEOUT = 30
    MAX_LOGIN_ATTEMPTS = 5