from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum
from sqlalchemy.sql import func
from database import Base  # 👈 IMPORTANTE (usar el mismo Base)
import enum


class UserRole(enum.Enum):
    ADMIN = "Admin"
    COMERCIAL = "Comercial"


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    usuario = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    rol = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SheetPrice(Base):
    __tablename__ = 'sheet_prices'

    id = Column(Integer, primary_key=True, index=True)
    material = Column(String, nullable=False)
    calibre = Column(Integer, nullable=False)
    peso_hoja = Column(Float, nullable=False)
    valor_unitario = Column(Float, nullable=False)
    fecha_actualizacion = Column(DateTime(timezone=True), server_default=func.now())


class BomTemplate(Base):
    __tablename__ = 'bom_templates'

    id = Column(Integer, primary_key=True, index=True)
    modelo_elevador = Column(String, nullable=False)
    parte = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    material_referencia = Column(String, nullable=False)
    peso_unitario = Column(Float, nullable=False)
    costo_base_materia_prima = Column(Float, nullable=False)
    es_transformacion = Column(Boolean, default=False)
    calibre_lamina = Column(Integer, nullable=True)


class CotizacionHistorico(Base):
    __tablename__ = 'cotizacion_historico'

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, nullable=True)
    modelo = Column(String, nullable=False)
    material = Column(String, nullable=False)
    calibres_json = Column(String, nullable=True)
    fecha_cotizacion = Column(DateTime(timezone=True), server_default=func.now())
    total_venta = Column(Float, nullable=False)
    notas = Column(String, nullable=True)