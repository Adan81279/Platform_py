# setup_admin.py 
import app as application  # Importamos el módulo completo, no las variables sueltas
from app.models import Usuario
import getpass

def crear_admin():
    # 1. Al ejecutar esto, la variable 'db' dentro del módulo 'app' deja de ser None
    flask_app = application.create_app()
    
    # 2. Ahora extraemos la 'db' directamente del módulo para tener la conexión real
    db_conectada = application.db
    
    with flask_app.app_context():
        print("\n" + "=" * 50)
        print("   CREAR USUARIO ADMINISTRADOR")
        print("=" * 50)
        
        # 3. Usamos la db_conectada (que ya no es None)
        admin_exists = db_conectada.users.find_one({'tipo_usuario': 1})
        
        if admin_exists:
            print(f"\nYa existe un administrador: {admin_exists['correo']}")
            respuesta = input("¿Deseas crear otro? (s/n): ")
            if respuesta.lower() != 's':
                print("Cancelado")
                return
        
        print("\nDatos del administrador:")
        nombre = input("Nombre completo [Administrador]: ") or "Administrador"
        correo = input("Correo electrónico [admin@apex.com]: ") or "admin@apex.com"
        
        while True:
            password = getpass.getpass("Contraseña (mínimo 6 caracteres): ")
            if len(password) < 6:
                print("La contraseña debe tener al menos 6 caracteres")
                continue
            confirm = getpass.getpass("Confirmar contraseña: ")
            if password != confirm:
                print("Las contraseñas no coinciden")
                continue
            break
        
        # 4. Pasamos la db_conectada al método del modelo
        result, message = Usuario.crear_usuario(db_conectada, nombre, correo, password, tipo_usuario=1)
        
        if result:
            print("\n¡ÉXITO! Administrador creado")
            print(f"   Nombre: {nombre}")
            print(f"   Correo: {correo}")
            # Nota: No imprimas la contraseña en producción, pero aquí sirve para confirmar
            print(f"   Contraseña: {password}")
            print("\nPuedes iniciar sesión en http://localhost:5000/login")
        else:
            print(f"\nError: {message}")

if __name__ == '__main__':
    crear_admin()