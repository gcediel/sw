"""
Modelos de base de datos y configuración SQLAlchemy
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, DECIMAL, BigInteger, Enum, TIMESTAMP, ForeignKey, Index, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import pymysql
from app.config import DB_CONFIG

# Crear URL de conexión
DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"

# Crear engine con pool de conexiones
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Verificar conexión antes de usar
    pool_recycle=3600,       # Reciclar conexiones cada hora
    pool_size=5,             # Tamaño del pool
    max_overflow=10,         # Conexiones adicionales
    echo=False               # Cambiar a True para debug SQL
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

# ============================================
# MODELOS
# ============================================

class Stock(Base):
    """Acciones monitorizadas"""
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(255))
    exchange = Column(String(50))
    active = Column(Boolean, default=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relaciones
    daily_data = relationship("DailyData", back_populates="stock", cascade="all, delete-orphan")
    weekly_data = relationship("WeeklyData", back_populates="stock", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="stock", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Stock(ticker='{self.ticker}', name='{self.name}')>"


class DailyData(Base):
    """Datos diarios de cotización (OHLC + Volumen)"""
    __tablename__ = 'daily_data'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(DECIMAL(12, 4))
    high = Column(DECIMAL(12, 4))
    low = Column(DECIMAL(12, 4))
    close = Column(DECIMAL(12, 4))
    volume = Column(BigInteger)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relación
    stock = relationship("Stock", back_populates="daily_data")
    
    __table_args__ = (
        Index('idx_stock_date', 'stock_id', 'date'),
        Index('idx_date', 'date'),
        Index('unique_stock_date', 'stock_id', 'date', unique=True),
    )
    
    def __repr__(self):
        return f"<DailyData(stock_id={self.stock_id}, date={self.date}, close={self.close})>"


class WeeklyData(Base):
    """Datos semanales agregados + análisis Weinstein"""
    __tablename__ = 'weekly_data'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    week_end_date = Column(Date, nullable=False)
    open = Column(DECIMAL(12, 4))
    high = Column(DECIMAL(12, 4))
    low = Column(DECIMAL(12, 4))
    close = Column(DECIMAL(12, 4))
    volume = Column(BigInteger)
    ma30 = Column(DECIMAL(12, 4))
    ma30_slope = Column(DECIMAL(8, 4))
    stage = Column(Integer)  # 1, 2, 3, 4 o NULL
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Relación
    stock = relationship("Stock", back_populates="weekly_data")
    
    __table_args__ = (
        Index('idx_week_date', 'week_end_date'),
        Index('idx_stage', 'stage'),
        Index('unique_stock_week', 'stock_id', 'week_end_date', unique=True),
    )
    
    def __repr__(self):
        return f"<WeeklyData(stock_id={self.stock_id}, week={self.week_end_date}, stage={self.stage})>"


class Signal(Base):
    """Señales de trading (BUY/SELL/STAGE_CHANGE)"""
    __tablename__ = 'signals'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    signal_date = Column(Date, nullable=False)
    signal_type = Column(Enum('BUY', 'SELL', 'STAGE_CHANGE'), nullable=False)
    stage_from = Column(Integer)
    stage_to = Column(Integer)
    price = Column(DECIMAL(12, 4))
    ma30 = Column(DECIMAL(12, 4))
    notified = Column(Boolean, default=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relación
    stock = relationship("Stock", back_populates="signals")
    
    __table_args__ = (
        Index('idx_signal_date', 'signal_date'),
        Index('idx_notified', 'notified'),
        Index('idx_stock_signal', 'stock_id', 'signal_date'),
        Index('uq_stock_signal_type', 'stock_id', 'signal_date', 'signal_type', unique=True),
    )
    
    def __repr__(self):
        return f"<Signal(stock_id={self.stock_id}, type={self.signal_type}, date={self.signal_date})>"


class Position(Base):
    """Posiciones de cartera (compras/ventas reales)"""
    __tablename__ = 'positions'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    stock_id    = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False)
    entry_date  = Column(Date, nullable=False)
    entry_price = Column(DECIMAL(12, 4), nullable=False)
    quantity    = Column(DECIMAL(12, 4), nullable=False)
    stop_loss   = Column(DECIMAL(12, 4), nullable=False)
    exit_date   = Column(Date, nullable=True)
    exit_price  = Column(DECIMAL(12, 4), nullable=True)
    status      = Column(String(10), default='OPEN')   # 'OPEN' | 'CLOSED'
    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.now)
    updated_at  = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    stock = relationship('Stock', backref='positions')

    __table_args__ = (
        Index('idx_position_status', 'status'),
    )

    def __repr__(self):
        return f"<Position(stock_id={self.stock_id}, status={self.status}, entry_date={self.entry_date})>"


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def init_db():
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(bind=engine)
    print("✓ Base de datos inicializada correctamente")
    print(f"✓ Tablas creadas: {', '.join([table.name for table in Base.metadata.sorted_tables])}")


def get_db():
    """
    Generador de sesión de base de datos
    Uso en FastAPI:
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    """Probar conexión a la base de datos"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        print("✓ Conexión a base de datos exitosa")
        return True
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        return False


if __name__ == '__main__':
    # Script de prueba
    print("Probando conexión a base de datos...")
    test_connection()
    
    print("\nCreando tablas...")
    init_db()
