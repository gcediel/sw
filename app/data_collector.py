"""
Recolector de datos del mercado usando múltiples fuentes
Soporta: Twelve Data (principal), yfinance (fallback)
"""
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import Stock, DailyData, SessionLocal
from app.config import (
    RATE_LIMIT_DELAY, MAX_RETRIES, RETRY_DELAY,
    TWELVEDATA_API_KEY, DATA_SOURCES
)

# Importar fuentes de datos
try:
    from twelvedata import TDClient
    TWELVEDATA_AVAILABLE = True
except ImportError:
    TWELVEDATA_AVAILABLE = False
    logging.warning("twelvedata no disponible, instalar con: pip install twelvedata")

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logging.warning("yfinance no disponible")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataCollector:
    """Recolector de datos usando múltiples fuentes con fallback automático"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Inicializar clientes
        self.td_client = None
        if TWELVEDATA_AVAILABLE and TWELVEDATA_API_KEY:
            try:
                self.td_client = TDClient(apikey=TWELVEDATA_API_KEY)
                logger.info("✓ Twelve Data cliente inicializado")
            except Exception as e:
                logger.warning(f"No se pudo inicializar Twelve Data: {e}")
    
    def _normalize_ticker_for_twelvedata(self, ticker: str) -> str:
        """
        Convertir ticker de formato Yahoo a formato Twelve Data
        
        Ejemplos:
            SAN.MC → SAN:BME
            TEF.MC → TEF:BME
            AAPL → AAPL (sin cambios)
        """
        # Mapeo de sufijos Yahoo → Twelve Data
        mapping = {
            '.MC': ':BME',      # Madrid
            '.L': ':LSE',       # London
            '.PA': ':EPA',      # Paris
            '.DE': ':XETRA',    # Frankfurt
            '.MI': ':MIL',      # Milan
            '.AS': ':AMS',      # Amsterdam
        }
        
        for yahoo_suffix, td_suffix in mapping.items():
            if ticker.endswith(yahoo_suffix):
                return ticker.replace(yahoo_suffix, td_suffix)
        
        # Si no tiene sufijo, asumimos US
        return ticker
    
    def _normalize_ticker_for_yfinance(self, ticker: str) -> str:
        """
        Convertir ticker de formato Twelve Data a Yahoo
        (inverso del anterior, por si se usa como fallback)
        """
        mapping = {
            ':BME': '.MC',
            ':LSE': '.L',
            ':EPA': '.PA',
            ':XETRA': '.DE',
            ':MIL': '.MI',
            ':AMS': '.AS',
        }
        
        for td_suffix, yahoo_suffix in mapping.items():
            if ticker.endswith(td_suffix):
                return ticker.replace(td_suffix, yahoo_suffix)
        
        return ticker
    
    def download_with_twelvedata(self, ticker: str, start_date: str, end_date: Optional[str] = None) -> Optional[Dict]:
        """Descargar datos usando Twelve Data API"""
        
        if not self.td_client:
            logger.debug("Twelve Data no disponible")
            return None
        
        try:
            # Normalizar ticker para Twelve Data
            td_ticker = self._normalize_ticker_for_twelvedata(ticker)
            logger.debug(f"Twelve Data: Descargando {td_ticker} (original: {ticker})")
            
            # Calcular fechas
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            # Descargar datos históricos
            ts = self.td_client.time_series(
                symbol=td_ticker,
                interval="1day",
                start_date=start_date,
                end_date=end_date,
                outputsize=5000
            )
            
            # Convertir a DataFrame
            df = ts.as_pandas()
            
            if df.empty:
                logger.warning(f"Twelve Data: No hay datos para {ticker}")
                return None
            
            # Resetear índice para tener fecha como columna
            df = df.reset_index()
            
            # Normalizar columnas (Twelve Data usa minúsculas)
            # El índice puede llamarse 'datetime' o mantener su nombre original
            if 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'Date'})
            elif df.columns[0] != 'Date':
                # Si la primera columna no es 'Date', asumimos que es la fecha
                df = df.rename(columns={df.columns[0]: 'Date'})
            
            df = df.rename(columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            
            # Obtener info de la acción
            try:
                quote = self.td_client.quote(symbol=td_ticker).as_json()
                stock_name = quote.get('name', ticker)
                exchange = quote.get('exchange', 'UNKNOWN')
            except:
                stock_name = ticker
                exchange = 'UNKNOWN'
            
            logger.debug(f"✓ Twelve Data: {ticker} → {len(df)} registros")
            
            return {
                'data': df,
                'name': stock_name,
                'exchange': exchange
            }
            
        except Exception as e:
            logger.debug(f"Twelve Data falló para {ticker}: {e}")
            return None
    
    def download_with_yfinance(self, ticker: str, start_date: str, end_date: Optional[str] = None) -> Optional[Dict]:
        """Descargar datos usando yfinance"""
        
        if not YFINANCE_AVAILABLE:
            logger.debug("yfinance no disponible")
            return None
        
        try:
            # Asegurar que el ticker está en formato Yahoo
            yf_ticker = self._normalize_ticker_for_yfinance(ticker)
            logger.debug(f"yfinance: Descargando {yf_ticker}")
            
            stock = yf.Ticker(yf_ticker)
            
            # Descargar datos históricos
            if end_date:
                data = stock.history(start=start_date, end=end_date, auto_adjust=False)
            else:
                data = stock.history(start=start_date, auto_adjust=False)
            
            if data.empty:
                logger.warning(f"yfinance: No hay datos para {ticker}")
                return None
            
            # Resetear índice
            data = data.reset_index()
            
            # Obtener información
            try:
                info = stock.info
                stock_name = info.get('longName', info.get('shortName', ticker))
                exchange = info.get('exchange', 'UNKNOWN')
            except:
                stock_name = ticker
                exchange = 'UNKNOWN'
            
            logger.debug(f"✓ yfinance: {ticker} → {len(data)} registros")
            
            return {
                'data': data,
                'name': stock_name,
                'exchange': exchange
            }
            
        except Exception as e:
            logger.debug(f"yfinance falló para {ticker}: {e}")
            return None
    
    def download_stock_data(self, ticker: str, start_date: str, end_date: Optional[str] = None, retries: int = 0) -> Optional[Dict]:
        """
        Descargar datos usando múltiples fuentes con fallback
        
        Args:
            ticker: Símbolo del ticker
            start_date: Fecha inicio (YYYY-MM-DD)
            end_date: Fecha fin (YYYY-MM-DD), None para hoy
            retries: Número de reintento actual
        
        Returns:
            Dict con 'data' (DataFrame), 'name' y 'exchange', o None
        """
        
        # Intentar con cada fuente en orden de prioridad
        for source in DATA_SOURCES:
            logger.debug(f"Intentando con {source} para {ticker}...")
            
            data_dict = None
            
            if source == 'twelvedata':
                data_dict = self.download_with_twelvedata(ticker, start_date, end_date)
            elif source == 'yfinance':
                data_dict = self.download_with_yfinance(ticker, start_date, end_date)
            
            if data_dict:
                logger.info(f"✓ {ticker}: {len(data_dict['data'])} registros (fuente: {source})")
                return data_dict
        
        # Si todas las fuentes fallaron, reintentar
        if retries < MAX_RETRIES:
            wait_time = RETRY_DELAY * (retries + 1)
            logger.warning(f"⚠ {ticker}: Todas las fuentes fallaron, reintento {retries + 1}/{MAX_RETRIES} en {wait_time}s")
            time.sleep(wait_time)
            return self.download_stock_data(ticker, start_date, end_date, retries + 1)
        
        logger.error(f"✗ {ticker}: Error definitivo después de {MAX_RETRIES} reintentos con todas las fuentes")
        return None
    
    def save_daily_data(self, stock_id: int, ticker: str, data_dict: Dict) -> int:
        """
        Guardar o actualizar datos diarios en la base de datos
        
        Args:
            stock_id: ID de la acción
            ticker: Ticker (para logs)
            data_dict: Diccionario con el DataFrame de datos
        
        Returns:
            Número de registros guardados/actualizados
        """
        data = data_dict['data']
        saved_count = 0
        updated_count = 0
        
        for _, row in data.iterrows():
            try:
                # Obtener fecha de forma robusta
                # Puede estar en 'Date', 'date', 'datetime', o ser el índice
                date_value = None
                if 'Date' in row.index:
                    date_value = row['Date']
                elif 'date' in row.index:
                    date_value = row['date']
                elif 'datetime' in row.index:
                    date_value = row['datetime']
                else:
                    # Si no encontramos la columna, usar el índice original
                    date_value = row.name if hasattr(row, 'name') else None
                
                if date_value is None:
                    logger.warning(f"No se pudo obtener fecha para registro de {ticker}")
                    continue
                
                # Convertir a objeto date
                if isinstance(date_value, str):
                    date_obj = pd.to_datetime(date_value).date()
                else:
                    date_obj = date_value.date() if hasattr(date_value, 'date') else date_value
                
                # Verificar si ya existe
                existing = self.db.query(DailyData).filter(
                    and_(
                        DailyData.stock_id == stock_id,
                        DailyData.date == date_obj
                    )
                ).first()
                
                if existing:
                    # Actualizar
                    existing.open = float(row['Open'])
                    existing.high = float(row['High'])
                    existing.low = float(row['Low'])
                    existing.close = float(row['Close'])
                    existing.volume = int(row['Volume']) if pd.notna(row['Volume']) else 0
                    updated_count += 1
                else:
                    # Insertar
                    daily_data = DailyData(
                        stock_id=stock_id,
                        date=date_obj,
                        open=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        volume=int(row['Volume']) if pd.notna(row['Volume']) else 0
                    )
                    self.db.add(daily_data)
                    saved_count += 1
                
            except Exception as e:
                logger.error(f"✗ Error guardando dato de {ticker}: {e}")
                continue
        
        try:
            self.db.commit()
            if saved_count > 0 or updated_count > 0:
                logger.info(f"✓ {ticker}: {saved_count} nuevos, {updated_count} actualizados")
            return saved_count + updated_count
        except Exception as e:
            self.db.rollback()
            logger.error(f"✗ Error en commit para {ticker}: {e}")
            return 0
    
    def load_historical_data(self, ticker: str, years: int = 2) -> bool:
        """
        Cargar datos históricos completos
        
        Args:
            ticker: Símbolo del ticker
            years: Años de histórico (default: 2 años ≈ 104 semanas)
        
        Returns:
            True si se cargó correctamente
        """
        # Calcular fechas
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        logger.info(f"📥 Descargando histórico de {ticker} desde {start_date.date()}")
        
        # Descargar datos
        data_dict = self.download_stock_data(
            ticker,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not data_dict:
            return False
        
        # Crear o actualizar stock
        stock = self.db.query(Stock).filter(Stock.ticker == ticker).first()
        
        if not stock:
            stock = Stock(
                ticker=ticker,
                name=data_dict['name'],
                exchange=data_dict['exchange'],
                active=True
            )
            self.db.add(stock)
            self.db.commit()
            self.db.refresh(stock)
            logger.info(f"✓ Stock {ticker} creado: {stock.name}")
        else:
            stock.name = data_dict['name']
            stock.exchange = data_dict['exchange']
            self.db.commit()
            logger.debug(f"✓ Stock {ticker} actualizado")
        
        # Guardar datos
        saved = self.save_daily_data(stock.id, ticker, data_dict)
        
        # Pausa para respetar rate limits
        time.sleep(RATE_LIMIT_DELAY)
        
        return saved > 0
    
    def update_daily_data(self, ticker: str, days_back: int = 5) -> bool:
        """
        Actualizar datos recientes
        
        Args:
            ticker: Símbolo del ticker
            days_back: Días hacia atrás (default: 5)
        
        Returns:
            True si se actualizó correctamente
        """
        # Buscar stock
        stock = self.db.query(Stock).filter(Stock.ticker == ticker).first()
        
        if not stock:
            logger.warning(f"⚠ Stock {ticker} no encontrado, cargando histórico completo...")
            return self.load_historical_data(ticker)
        
        # Calcular fecha de inicio
        start_date = datetime.now() - timedelta(days=days_back)
        
        logger.info(f"🔄 Actualizando {ticker} desde {start_date.date()}")
        
        # Descargar datos recientes
        data_dict = self.download_stock_data(
            ticker,
            start_date.strftime('%Y-%m-%d')
        )
        
        if not data_dict:
            return False
        
        # Guardar/actualizar
        saved = self.save_daily_data(stock.id, ticker, data_dict)
        
        # Pausa
        time.sleep(RATE_LIMIT_DELAY)
        
        return saved > 0


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def add_stock_to_monitor(ticker: str, name: str = None, exchange: str = None) -> Optional[int]:
    """Añadir una acción a la lista de seguimiento"""
    db = SessionLocal()
    try:
        existing = db.query(Stock).filter(Stock.ticker == ticker).first()
        if existing:
            logger.info(f"ℹ {ticker} ya existe (ID: {existing.id})")
            return existing.id
        
        stock = Stock(
            ticker=ticker,
            name=name or ticker,
            exchange=exchange or 'UNKNOWN',
            active=True
        )
        db.add(stock)
        db.commit()
        db.refresh(stock)
        logger.info(f"✓ Stock {ticker} añadido con ID {stock.id}")
        return stock.id
    except Exception as e:
        logger.error(f"✗ Error añadiendo {ticker}: {e}")
        return None
    finally:
        db.close()


def get_active_stocks() -> List[Stock]:
    """Obtener todas las acciones activas"""
    db = SessionLocal()
    try:
        return db.query(Stock).filter(Stock.active == True).all()
    finally:
        db.close()


if __name__ == '__main__':
    # Script de prueba
    print("=== TEST DATA COLLECTOR MULTI-FUENTE ===\n")
    
    print(f"Twelve Data disponible: {TWELVEDATA_AVAILABLE}")
    print(f"yfinance disponible: {YFINANCE_AVAILABLE}")
    print(f"Fuentes configuradas: {DATA_SOURCES}\n")
    
    db = SessionLocal()
    collector = DataCollector(db)
    
    # Probar con una acción
    test_ticker = "AAPL"
    print(f"Probando descarga de {test_ticker}...")
    success = collector.load_historical_data(test_ticker, years=1)
    
    if success:
        print(f"\n✓ Datos de {test_ticker} cargados correctamente")
        
        stock = db.query(Stock).filter(Stock.ticker == test_ticker).first()
        count = db.query(DailyData).filter(DailyData.stock_id == stock.id).count()
        
        print(f"✓ Stock ID: {stock.id}")
        print(f"✓ Nombre: {stock.name}")
        print(f"✓ Registros: {count}")
    else:
        print(f"\n✗ Error cargando {test_ticker}")
    
    db.close()
