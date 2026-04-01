# app/backup_utils.py
import os
import subprocess
import gzip
import shutil
import json
from datetime import datetime, timedelta
from bson import ObjectId
from flask import current_app
import sys
import platform
import string

class BackupManager:
    """Clase para gestionar backups de MongoDB"""
    
    def __init__(self, db, backup_dir=None):
        self.db = db
        self.backup_dir = backup_dir or os.path.join(current_app.root_path, 'static', 'backups')
        self.usb_backup_dir = 'backups/auto_apex'  # Carpeta en USB
        
    def ensure_backup_dir(self):
        """Asegura que exista el directorio de backups"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
    
    def get_collections_list(self):
        """Obtiene la lista de colecciones a respaldar"""
        collections = ['users', 'vehiculos', 'materiales', 'lugares', 'historial_uso']
        return [col for col in collections if col in self.db.list_collection_names()]
    
    def convert_to_serializable(self, obj):
        """Convierte objetos de MongoDB a tipos serializables JSON"""
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            # Convertir bytes a string hexadecimal o base64
            # Para contraseñas hasheadas, es mejor guardar como string
            try:
                return obj.decode('utf-8')
            except UnicodeDecodeError:
                # Si no se puede decodificar como UTF-8, usar base64
                import base64
                return base64.b64encode(obj).decode('utf-8')
        elif isinstance(obj, dict):
            return {k: self.convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_to_serializable(item) for item in obj]
        elif isinstance(obj, float):
            return obj
        elif isinstance(obj, int):
            return obj
        elif isinstance(obj, str):
            return obj
        elif obj is None:
            return None
        else:
            # Para cualquier otro tipo, convertir a string
            return str(obj)
    
    def backup_collection(self, collection_name, backup_path):
        """Respalda una colección individual"""
        try:
            collection_data = list(self.db[collection_name].find())
            # Convertir usando la función recursiva
            collection_data = self.convert_to_serializable(collection_data)
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(collection_data, f, ensure_ascii=False, indent=2)
            return True, len(collection_data)
        except Exception as e:
            return False, str(e)
    
    def create_backup(self, backup_type='complete', filename=None, compress=True):
        """Crea un backup de la base de datos"""
        self.ensure_backup_dir()
        
        # Generar nombre de archivo si no se proporciona
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backup_{backup_type}_{timestamp}.json"
        
        base_path = os.path.join(self.backup_dir, filename)
        final_path = base_path + '.gz' if compress else base_path
        
        try:
            # Obtener colecciones a respaldar
            collections = self.get_collections_list()
            backup_data = {
                'metadata': {
                    'type': backup_type,
                    'created_at': datetime.now().isoformat(),
                    'database': 'apex_auto_system',
                    'collections_count': len(collections),
                    'collections': collections
                },
                'data': {}
            }
            
            total_records = 0
            
            # Dependiendo del tipo de backup
            if backup_type == 'complete':
                # Respaldo completo de todas las colecciones
                for col in collections:
                    data = list(self.db[col].find())
                    # Convertir usando la función recursiva
                    data = self.convert_to_serializable(data)
                    backup_data['data'][col] = data
                    total_records += len(data)
            
            elif backup_type == 'differential':
                # Respaldo de todas las colecciones (simplificado por ahora)
                for col in collections:
                    data = list(self.db[col].find())
                    data = self.convert_to_serializable(data)
                    backup_data['data'][col] = data
                    total_records += len(data)
            
            elif backup_type == 'incremental':
                # Respaldo de los últimos documentos (limitado a 100 por colección)
                for col in collections:
                    data = list(self.db[col].find().limit(100))
                    data = self.convert_to_serializable(data)
                    backup_data['data'][col] = data
                    total_records += len(data)
            
            backup_data['metadata']['total_records'] = total_records
            backup_data_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
            backup_data['metadata']['size_bytes'] = len(backup_data_json.encode('utf-8'))
            
            # Guardar archivo
            with open(base_path, 'w', encoding='utf-8') as f:
                f.write(backup_data_json)
            
            # Comprimir si es necesario
            if compress:
                with open(base_path, 'rb') as f_in:
                    with gzip.open(final_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(base_path)
            
            # Registrar en la base de datos
            backup_record = {
                'filename': os.path.basename(final_path),
                'type': backup_type,
                'status': 'completed',
                'size_bytes': os.path.getsize(final_path),
                'size_formatted': self.format_size(os.path.getsize(final_path)),
                'backup_date': datetime.now(),
                'expires_at': self.calculate_expiry(backup_type),
                'tables_count': len(collections),
                'tables_list': collections,
                'total_records': total_records,
                'file_path': final_path,
                'storage_device': 'local',
                'created_by': None,  # Se puede obtener de current_user si está disponible
                'database_name': 'apex_auto_system',
                'error_message': None
            }
            
            # Intentar obtener el usuario actual si está disponible
            try:
                from flask_login import current_user
                if current_user and hasattr(current_user, 'id'):
                    backup_record['created_by'] = current_user.id
            except:
                pass
            
            result = self.db.backups.insert_one(backup_record)
            backup_record['_id'] = str(result.inserted_id)
            backup_record['backup_date'] = backup_record['backup_date'].strftime('%d/%m/%Y %H:%M')
            if backup_record['expires_at']:
                backup_record['expires_at'] = backup_record['expires_at'].strftime('%d/%m/%Y %H:%M')
            
            return True, backup_record
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def calculate_expiry(self, backup_type):
        """Calcula la fecha de expiración según el tipo de backup"""
        now = datetime.now()
        if backup_type == 'complete':
            return now + timedelta(days=30)
        elif backup_type == 'differential':
            return now + timedelta(days=15)
        elif backup_type == 'incremental':
            return now + timedelta(days=7)
        return None
    
    def format_size(self, bytes_size):
        """Formatea el tamaño en bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"
    
    def get_backup_stats(self):
        """Obtiene estadísticas de los backups"""
        try:
            total = self.db.backups.count_documents({})
            complete = self.db.backups.count_documents({'type': 'complete'})
            differential = self.db.backups.count_documents({'type': 'differential'})
            incremental = self.db.backups.count_documents({'type': 'incremental'})
            expired = self.db.backups.count_documents({'expires_at': {'$lt': datetime.now()}})
            
            # Calcular tamaño total
            pipeline = [
                {'$group': {
                    '_id': None,
                    'total_size': {'$sum': '$size_bytes'}
                }}
            ]
            result = list(self.db.backups.aggregate(pipeline))
            total_size_bytes = result[0]['total_size'] if result else 0
            total_size_mb = total_size_bytes / (1024 * 1024)
            
            return {
                'total': total,
                'complete': complete,
                'differential': differential,
                'incremental': incremental,
                'expired_count': expired,
                'total_size_mb': total_size_mb,
                'total_size_formatted': self.format_size(total_size_bytes)
            }
        except Exception as e:
            return {
                'total': 0,
                'complete': 0,
                'differential': 0,
                'incremental': 0,
                'expired_count': 0,
                'total_size_mb': 0,
                'total_size_formatted': '0 B'
            }
    
    def get_disk_usage(self):
        """Obtiene información de uso de disco"""
        try:
            # Intentar usar psutil si está instalado
            try:
                import psutil
                disk = psutil.disk_usage(self.backup_dir if os.path.exists(self.backup_dir) else '/')
                return {
                    'disk_percent': disk.percent,
                    'disk_free': self.format_size(disk.free),
                    'disk_used': self.format_size(disk.used),
                    'disk_total': self.format_size(disk.total)
                }
            except ImportError:
                # Si no está psutil, calcular manualmente
                total_size = 0
                if os.path.exists(self.backup_dir):
                    for root, dirs, files in os.walk(self.backup_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                            except:
                                pass
                
                # Estimar porcentaje (no muy preciso sin psutil)
                return {
                    'disk_percent': 0,
                    'disk_free': 'No disponible',
                    'disk_used': self.format_size(total_size),
                    'disk_total': 'No disponible'
                }
        except Exception as e:
            return {
                'disk_percent': 0,
                'disk_free': 'Error',
                'disk_used': 'Error',
                'disk_total': 'Error'
            }
    
    def delete_backup(self, backup_id):
        """Elimina un backup"""
        try:
            backup = self.db.backups.find_one({'_id': ObjectId(backup_id)})
            if backup:
                # Eliminar archivo físico
                if os.path.exists(backup['file_path']):
                    os.remove(backup['file_path'])
                # Eliminar registro
                self.db.backups.delete_one({'_id': ObjectId(backup_id)})
                return True, "Backup eliminado correctamente"
            return False, "Backup no encontrado"
        except Exception as e:
            return False, str(e)
    
    def cleanup_expired(self):
        """Elimina backups expirados"""
        try:
            expired = self.db.backups.find({'expires_at': {'$lt': datetime.now()}})
            deleted_count = 0
            for backup in expired:
                if os.path.exists(backup['file_path']):
                    os.remove(backup['file_path'])
                self.db.backups.delete_one({'_id': backup['_id']})
                deleted_count += 1
            return True, f"Se eliminaron {deleted_count} backups expirados"
        except Exception as e:
            return False, str(e)
    
    # ================ MÉTODOS MEJORADOS PARA DETECCIÓN DE USB ================
    
    def get_usb_drives_windows(self):
        """Detecta unidades USB en Windows usando WMIC (método mejorado)"""
        drives = []
        try:
            # Usar wmic con formato CSV para mejor parsing
            result = subprocess.run(
                ['wmic', 'logicaldisk', 'get', 'deviceid,volumename,size,freespace,drivetype', '/format:csv'],
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore'
            )
            
            # Parsear la salida CSV
            for line in result.stdout.split('\n'):
                if line and ',' in line:
                    parts = line.strip().split(',')
                    if len(parts) >= 5:
                        try:
                            # Formato: Node,DeviceID,DriveType,FreeSpace,Size,VolumeName
                            device_id = parts[1].strip() if len(parts) > 1 else ''
                            drive_type = parts[2].strip() if len(parts) > 2 else ''
                            free_space = parts[3].strip() if len(parts) > 3 else '0'
                            total_space = parts[4].strip() if len(parts) > 4 else '0'
                            
                            # DriveType 2 = Unidad removible (USB)
                            if drive_type == '2' and device_id:
                                total_space = int(total_space) if total_space.isdigit() else 0
                                free_space = int(free_space) if free_space.isdigit() else 0
                                
                                # Verificar si la unidad realmente existe
                                if os.path.exists(device_id):
                                    drives.append({
                                        'letter': device_id,
                                        'name': f'USB Drive {device_id}',
                                        'total_space': total_space,
                                        'free_space': free_space,
                                        'total_gb': total_space / (1024**3) if total_space > 0 else 0,
                                        'free_gb': free_space / (1024**3) if free_space > 0 else 0,
                                        'used_percentage': ((total_space - free_space) / total_space * 100) if total_space > 0 else 0,
                                        'is_writable': self.is_writable_drive(device_id),
                                        'backup_folder_exists': os.path.exists(f"{device_id}\\{self.usb_backup_dir}")
                                    })
                        except Exception as e:
                            print(f"Error parseando línea: {line}, Error: {e}")
                            
        except Exception as e:
            print(f"Error en WMIC: {e}")
            
        return drives
    
    def get_usb_drives_ctypes(self):
        """Detecta unidades USB usando ctypes (método más confiable)"""
        drives = []
        try:
            from ctypes import windll
            
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    try:
                        # Obtener tipo de unidad usando GetDriveTypeW
                        drive_type = windll.kernel32.GetDriveTypeW(drive)
                        # DRIVE_REMOVABLE = 2
                        if drive_type == 2:  # Unidad removible (USB)
                            total, free = self.get_disk_space_ctypes(drive)
                            drives.append({
                                'letter': drive,
                                'name': f'USB Drive {drive}',
                                'total_space': total,
                                'free_space': free,
                                'total_gb': total / (1024**3) if total > 0 else 0,
                                'free_gb': free / (1024**3) if free > 0 else 0,
                                'used_percentage': ((total - free) / total * 100) if total > 0 else 0,
                                'is_writable': self.is_writable_drive(drive),
                                'backup_folder_exists': os.path.exists(f"{drive}{self.usb_backup_dir}")
                            })
                    except Exception as e:
                        print(f"Error accediendo a {drive}: {e}")
                        
        except ImportError:
            print("ctypes no disponible")
        except Exception as e:
            print(f"Error en detección ctypes: {e}")
            
        return drives
    
    def get_disk_space_ctypes(self, path):
        """Obtiene espacio en disco usando ctypes - VERSIÓN CORREGIDA"""
        try:
            import ctypes
            
            # Preparar variables
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            total_free_bytes = ctypes.c_ulonglong(0)
            
            # Llamar a la función de Windows
            success = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(path),
                ctypes.byref(free_bytes),
                ctypes.byref(total_bytes),
                ctypes.byref(total_free_bytes)
            )
            
            if success:
                return total_bytes.value, free_bytes.value
            else:
                # Si falla, intentar con método alternativo usando shutil
                import shutil
                usage = shutil.disk_usage(path)
                return usage.total, usage.free
                
        except Exception as e:
            print(f"Error en get_disk_space_ctypes: {e}")
            # Método de respaldo con shutil
            try:
                import shutil
                usage = shutil.disk_usage(path)
                return usage.total, usage.free
            except:
                return 0, 0
    
    def is_writable_drive(self, drive_path):
        """Verifica si la unidad tiene permisos de escritura"""
        try:
            test_file = os.path.join(drive_path, 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except:
            return False
    
    def detect_all_drives(self):
        """Detecta todas las unidades disponibles (para debugging) - VERSIÓN MEJORADA"""
        drives = []
        
        try:
            from ctypes import windll
            import shutil
            
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    try:
                        drive_type = windll.kernel32.GetDriveTypeW(drive)
                        type_names = {
                            0: 'Desconocido',
                            1: 'No existe',
                            2: 'Removible (USB)',
                            3: 'Fijo (HDD/SSD)',
                            4: 'Red',
                            5: 'CD-ROM',
                            6: 'RAM Disk'
                        }
                        
                        # Usar shutil.disk_usage que es más confiable
                        try:
                            usage = shutil.disk_usage(drive)
                            total = usage.total
                            free = usage.free
                        except:
                            total = 0
                            free = 0
                        
                        drives.append({
                            'letter': drive,
                            'name': type_names.get(drive_type, 'Desconocido'),
                            'type_code': drive_type,
                            'type_name': type_names.get(drive_type, 'Desconocido'),
                            'total_space': total,
                            'free_space': free,
                            'total_gb': total / (1024**3) if total > 0 else 0,
                            'free_gb': free / (1024**3) if free > 0 else 0,
                            'is_usb': drive_type == 2,
                            'is_writable': self.is_writable_drive(drive)
                        })
                    except Exception as e:
                        print(f"Error accediendo a {drive}: {e}")
                        
        except Exception as e:
            print(f"Error en detección de unidades: {e}")
            
        return drives
    
    def get_usb_devices(self):
        """Obtiene todos los dispositivos USB detectados (método principal) - VERSIÓN MEJORADA"""
        drives = []
        
        print("🔍 Buscando dispositivos USB...")
        
        # Método 1: Usar ctypes (más confiable)
        drives = self.get_usb_drives_ctypes()
        if drives:
            print(f"✅ Detectados {len(drives)} USB con ctypes")
            for drive in drives:
                print(f"   - {drive['letter']}: {drive['total_gb']:.2f} GB total, {drive['free_gb']:.2f} GB libre")
        
        # Método 2: Si no se encontraron USB, intentar con WMIC
        if not drives:
            print("⚠️ No se detectaron USB con ctypes, usando WMIC...")
            drives = self.get_usb_drives_windows()
            if drives:
                print(f"✅ Detectados {len(drives)} USB con WMIC")
        
        # Método 3: Si aún no hay drives, mostrar todas las unidades para debugging
        if not drives:
            print("❌ No se detectaron USB, mostrando todas las unidades para diagnóstico:")
            all_drives = self.detect_all_drives()
            for drive in all_drives:
                if drive['type_code'] == 2:
                    print(f"   🔌 {drive['letter']} - {drive['type_name']} - {drive['total_gb']:.2f} GB")
                else:
                    print(f"   💾 {drive['letter']} - {drive['type_name']} - {drive['total_gb']:.2f} GB")
        
        return drives
    
    # ================ FIN MÉTODOS MEJORADOS PARA DETECCIÓN DE USB ================
    
    def create_usb_backup(self, drive_letter, backup_type='complete'):
        """Crea un backup directamente en USB"""
        try:
            usb_path = f"{drive_letter}\\{self.usb_backup_dir}"
            if not os.path.exists(usb_path):
                os.makedirs(usb_path)
            
            # Crear backup temporal
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backup_{backup_type}_{timestamp}.json.gz"
            filepath = os.path.join(usb_path, filename)
            
            # Crear backup
            collections = self.get_collections_list()
            backup_data = {
                'metadata': {
                    'type': backup_type,
                    'created_at': datetime.now().isoformat(),
                    'database': 'apex_auto_system',
                    'collections': collections
                },
                'data': {}
            }
            
            for col in collections:
                data = list(self.db[col].find())
                data = self.convert_to_serializable(data)
                backup_data['data'][col] = data
            
            # Guardar comprimido
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            return True, f"Backup creado exitosamente en {drive_letter}"
        except Exception as e:
            return False, str(e)
    
    def sync_to_usb(self, drive_letter, backup_id):
        """Sincroniza un backup existente a USB"""
        try:
            backup = self.db.backups.find_one({'_id': ObjectId(backup_id)})
            if not backup:
                return False, "Backup no encontrado"
            
            if not os.path.exists(backup['file_path']):
                return False, "Archivo de backup no encontrado"
            
            usb_path = f"{drive_letter}\\{self.usb_backup_dir}"
            if not os.path.exists(usb_path):
                os.makedirs(usb_path)
            
            dest_path = os.path.join(usb_path, backup['filename'])
            shutil.copy2(backup['file_path'], dest_path)
            
            return True, f"Backup sincronizado a {drive_letter}"
        except Exception as e:
            return False, str(e)
    
    def get_usb_files(self, drive_letter):
        """Lista archivos de backup en USB"""
        try:
            usb_path = f"{drive_letter}\\{self.usb_backup_dir}"
            if not os.path.exists(usb_path):
                return []
            
            files = []
            for file in os.listdir(usb_path):
                if file.endswith('.json.gz') or file.endswith('.json'):
                    file_path = os.path.join(usb_path, file)
                    stat = os.stat(file_path)
                    files.append({
                        'name': file,
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'is_backup': True
                    })
            return files
        except Exception as e:
            return []
    
    def import_from_usb(self, drive_letter, filename):
        """Importa un backup desde USB al sistema"""
        try:
            usb_path = f"{drive_letter}\\{self.usb_backup_dir}"
            file_path = os.path.join(usb_path, filename)
            
            if not os.path.exists(file_path):
                return False, "Archivo no encontrado en USB"
            
            # Copiar al directorio local
            dest_path = os.path.join(self.backup_dir, filename)
            shutil.copy2(file_path, dest_path)
            
            # Registrar en base de datos
            import gzip
            import json
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            backup_record = {
                'filename': filename,
                'type': backup_data['metadata']['type'],
                'status': 'completed',
                'size_bytes': os.path.getsize(dest_path),
                'size_formatted': self.format_size(os.path.getsize(dest_path)),
                'backup_date': datetime.fromisoformat(backup_data['metadata']['created_at']),
                'expires_at': self.calculate_expiry(backup_data['metadata']['type']),
                'tables_count': len(backup_data['metadata']['collections']),
                'tables_list': backup_data['metadata']['collections'],
                'file_path': dest_path,
                'storage_device': 'local',
                'created_by': None,
                'database_name': 'apex_auto_system',
                'error_message': None
            }
            
            self.db.backups.insert_one(backup_record)
            return True, "Backup importado exitosamente"
        except Exception as e:
            return False, str(e)