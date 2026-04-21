from passlib.context import CryptContext
from models import User

# Usar PBKDF2 (puro Python, sin límite de bytes, no requiere compilación)
# Si hay hashes bcrypt antiguos, CryptContext los sigue verificando
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],  # PBKDF2 primero, bcrypt como fallback
    deprecated="auto"
)


class AuthManager:
    def __init__(self, db):  # 👈 AQUÍ ESTÁ LA CLAVE
        self.db = db

    def hash_password(self, password):
        return pwd_context.hash(password)

    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def register_user(self, nombre, usuario, password, rol):
        user = User(
            nombre=nombre,
            usuario=usuario,
            password_hash=self.hash_password(password),
            rol=rol
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate_user(self, usuario, password):
        user = self.db.query(User).filter(User.usuario == usuario).first()

        if not user:
            return None

        if not self.verify_password(password, user.password_hash):
            return None

        return user