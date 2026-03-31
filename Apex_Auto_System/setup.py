# setup.py - Ejecutar una sola vez para crear admin
import app as application  # Importamos el módulo completo
from app.models import Usuario

# 1. Ejecutamos create_app() para que se asigne la variable 'db' global en el módulo app
flask_app = application.create_app()

# 2. Ahora accedemos a db a través del módulo 'application'
# de esta forma obtenemos el valor actualizado (ya no es None)
db_actualizada = application.db

with flask_app.app_context():
    # Verificar si ya existe admin usando la db actualizada
    admin = db_actualizada.users.find_one({'correo': 'admin@apex.com'})
    
    if not admin:
        Usuario.crear_usuario(
            db_actualizada,
            'Administrador',
            'admin@apex.com',
            'Admin123',
            tipo_usuario=1
        )
        print("✓ Usuario administrador creado")
        print("  Email: admin@apex.com")
        print("  Contraseña: Admin123")
    else:
        print("✓ El usuario administrador ya existe")