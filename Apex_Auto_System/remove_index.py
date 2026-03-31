# remove_index.py
from app import create_app, db
from pymongo.errors import OperationFailure

app = create_app()

with app.app_context():
    try:
        # Verificar índices existentes
        indexes = db.materiales.index_information()
        print("Índices actuales:", list(indexes.keys()))
        
        # Eliminar el índice problemático
        if 'clave_material_1' in indexes:
            db.materiales.drop_index('clave_material_1')
            print("✅ Índice 'clave_material_1' eliminado correctamente")
        elif 'clave_1' in indexes:
            db.materiales.drop_index('clave_1')
            print("✅ Índice 'clave_1' eliminado correctamente")
        else:
            print("⚠️ No se encontró el índice problemático")
            
        # Mostrar índices restantes
        print("\nÍndices restantes:", list(db.materiales.index_information().keys()))
        
    except Exception as e:
        print(f"❌ Error: {e}")