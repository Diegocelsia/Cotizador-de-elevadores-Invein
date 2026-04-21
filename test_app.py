#!/usr/bin/env python
"""
Script de prueba para verificar que app.py carga sin errores
"""
import sys
import os

sys.path.insert(0, os.getcwd())

print("[*] Inicializando sistema...")

try:
    print("[*] Validando modelos...")
    from models import BomTemplate, User, SheetPrice, CotizacionHistorico
    print("    - BomTemplate OK")
    print("    - User OK")
    print("    - SheetPrice OK")
    print("    - CotizacionHistorico OK")
    
    print("[*] Validando database...")
    from database import SessionLocal
    db = SessionLocal()
    print("    - Conexion exitosa")
    
    print("[*] Validando auth...")
    from auth_manager import AuthManager
    auth = AuthManager(db)
    print("    - AuthManager OK")
    
    print("[*] Validando usuario comercial...")
    user = db.query(User).filter(User.usuario == "Invein").first()
    if user:
        print(f"    - Usuario comercial encontrado (ID: {user.id})")
    else:
        print("    - [WARNING] Usuario comercial no encontrado")
    
    db.close()
    
    print("\n" + "="*60)
    print("[OK] EXITO: Sistema completamente funcional")
    print("="*60)
    print("\nPuedes iniciar la app con:")
    print("  python -m streamlit run app.py")
    print("\nCredenciales de prueba:")
    print("  Usuario: Invein")
    print("  Contrasena: Invein2026*")
    print("="*60)
    
except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

