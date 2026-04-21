#!/usr/bin/env python
"""
Crea o actualiza el unico usuario comercial por defecto.
"""

from auth_manager import AuthManager
from database import SessionLocal
from models import User, UserRole


def main() -> int:
    db = SessionLocal()
    try:
        auth = AuthManager(db)
        username = "Invein"
        password = "Invein2026*"

        db.query(User).delete()
        db.commit()

        auth.register_user(
            nombre="Invein",
            usuario=username,
            password=password,
            rol=UserRole.COMERCIAL,
        )
        print("[OK] Usuario comercial creado")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())