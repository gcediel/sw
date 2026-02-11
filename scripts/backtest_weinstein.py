#!/usr/bin/env python3
"""
Backtesting del Sistema Weinstein
Evalúa el rendimiento de las señales BUY históricas

Métricas:
- % de operaciones ganadoras
- Retorno promedio, máximo, mínimo
- Comparación con buy & hold
- Análisis por horizonte temporal

Uso:
    python scripts/backtest_weinstein.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from datetime import datetime, timedelta
from app.database import SessionLocal, Stock, Signal, DailyData
from sqlalchemy import and_
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/backtest.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WeinsteinBacktest:
    """Backtesting de señales Weinstein"""
    
    def __init__(self, db):
        self.db = db
        self.results = []
    
    def get_price_at_date(self, stock_id: int, target_date, days_tolerance: int = 5):
        """
        Obtener precio de cierre en una fecha específica
        Si no hay datos exactos, busca el día más cercano
        """
        # Buscar precio exacto
        exact = self.db.query(DailyData).filter(
            and_(
                DailyData.stock_id == stock_id,
                DailyData.date == target_date
            )
        ).first()
        
        if exact:
            return float(exact.close), exact.date
        
        # Buscar día más cercano (hacia adelante)
        for i in range(1, days_tolerance + 1):
            next_date = target_date + timedelta(days=i)
            result = self.db.query(DailyData).filter(
                and_(
                    DailyData.stock_id == stock_id,
                    DailyData.date == next_date
                )
            ).first()
            
            if result:
                return float(result.close), result.date
        
        return None, None
    
    def get_current_price(self, stock_id: int):
        """Obtener último precio disponible"""
        latest = self.db.query(DailyData).filter(
            DailyData.stock_id == stock_id
        ).order_by(DailyData.date.desc()).first()
        
        if latest:
            return float(latest.close), latest.date
        
        return None, None
    
    def calculate_returns(self, entry_price: float, exit_price: float) -> dict:
        """Calcular métricas de retorno"""
        if not entry_price or not exit_price:
            return None
        
        absolute_return = exit_price - entry_price
        percent_return = (absolute_return / entry_price) * 100
        
        return {
            'absolute': absolute_return,
            'percent': percent_return
        }
    
    def backtest_signal(self, signal, horizons: list = [30, 90, 180, 365]):
        """
        Backtest de una señal individual
        
        Args:
            signal: Objeto Signal de la BD
            horizons: Lista de horizontes temporales en días
        """
        stock = self.db.query(Stock).filter(Stock.id == signal.stock_id).first()
        
        if not stock:
            return None
        
        # Precio de entrada (señal)
        entry_price = float(signal.price)
        entry_date = signal.signal_date
        
        result = {
            'ticker': stock.ticker,
            'name': stock.name,
            'entry_date': entry_date,
            'entry_price': entry_price,
            'signal_type': signal.signal_type,
            'stage_transition': f"{signal.stage_from} → {signal.stage_to}",
            'horizons': {}
        }
        
        # Calcular retornos en diferentes horizontes
        for days in horizons:
            exit_date = entry_date + timedelta(days=days)
            exit_price, actual_exit_date = self.get_price_at_date(
                signal.stock_id, 
                exit_date
            )
            
            if exit_price:
                returns = self.calculate_returns(entry_price, exit_price)
                result['horizons'][days] = {
                    'exit_date': actual_exit_date,
                    'exit_price': exit_price,
                    'return_pct': returns['percent'],
                    'return_abs': returns['absolute'],
                    'winner': returns['percent'] > 0
                }
        
        # Retorno hasta hoy (holding actual)
        current_price, current_date = self.get_current_price(signal.stock_id)
        if current_price:
            returns = self.calculate_returns(entry_price, current_price)
            result['current'] = {
                'date': current_date,
                'price': current_price,
                'return_pct': returns['percent'],
                'return_abs': returns['absolute'],
                'winner': returns['percent'] > 0,
                'days_held': (current_date - entry_date).days
            }
        
        return result
    
    def run_backtest(self, signal_type: str = 'BUY'):
        """
        Ejecutar backtest completo
        
        Args:
            signal_type: Tipo de señal a evaluar ('BUY', 'SELL', etc.)
        """
        logger.info("=" * 60)
        logger.info(f"BACKTESTING - Señales {signal_type}")
        logger.info("=" * 60)
        
        # Obtener señales del tipo especificado
        signals = self.db.query(Signal).filter(
            Signal.signal_type == signal_type
        ).order_by(Signal.signal_date.desc()).all()
        
        if not signals:
            logger.warning(f"No hay señales de tipo {signal_type}")
            return None
        
        logger.info(f"\nTotal señales {signal_type}: {len(signals)}")
        logger.info(f"Analizando retornos en horizontes: 1m, 3m, 6m, 1a, actual\n")
        
        # Procesar cada señal
        for idx, signal in enumerate(signals, 1):
            logger.info(f"[{idx}/{len(signals)}] Analizando señal...")
            
            result = self.backtest_signal(signal, horizons=[30, 90, 180, 365])
            
            if result:
                self.results.append(result)
                
                # Log básico
                ticker = result['ticker']
                entry = result['entry_date']
                
                if 'current' in result:
                    current_return = result['current']['return_pct']
                    logger.info(f"  {ticker} ({entry}): {current_return:+.2f}% (actual)")
        
        return self.results
    
    def calculate_statistics(self):
        """Calcular estadísticas agregadas del backtest"""
        
        if not self.results:
            return None
        
        stats = {
            'total_signals': len(self.results),
            'horizons': {}
        }
        
        # Estadísticas por horizonte
        horizons = [30, 90, 180, 365, 'current']
        
        for horizon in horizons:
            returns = []
            winners = 0
            losers = 0
            
            for result in self.results:
                if horizon == 'current':
                    if 'current' in result:
                        ret = result['current']['return_pct']
                        returns.append(ret)
                        if ret > 0:
                            winners += 1
                        else:
                            losers += 1
                else:
                    if horizon in result['horizons']:
                        ret = result['horizons'][horizon]['return_pct']
                        returns.append(ret)
                        if ret > 0:
                            winners += 1
                        else:
                            losers += 1
            
            if returns:
                stats['horizons'][horizon] = {
                    'count': len(returns),
                    'winners': winners,
                    'losers': losers,
                    'win_rate': (winners / len(returns)) * 100 if returns else 0,
                    'avg_return': sum(returns) / len(returns),
                    'max_return': max(returns),
                    'min_return': min(returns),
                    'positive_avg': sum([r for r in returns if r > 0]) / winners if winners > 0 else 0,
                    'negative_avg': sum([r for r in returns if r < 0]) / losers if losers > 0 else 0
                }
        
        return stats
    
    def print_report(self, stats):
        """Imprimir reporte detallado"""
        
        if not stats:
            logger.warning("No hay estadísticas para mostrar")
            return
        
        logger.info("\n" + "=" * 60)
        logger.info("REPORTE DE BACKTESTING")
        logger.info("=" * 60)
        
        logger.info(f"\nTotal de señales analizadas: {stats['total_signals']}")
        
        # Tabla de resultados por horizonte
        horizon_names = {
            30: '1 mes (30d)',
            90: '3 meses (90d)',
            180: '6 meses (180d)',
            365: '1 año (365d)',
            'current': 'Actual (hold)'
        }
        
        logger.info("\n" + "=" * 60)
        logger.info("RESULTADOS POR HORIZONTE TEMPORAL")
        logger.info("=" * 60)
        
        for horizon in [30, 90, 180, 365, 'current']:
            if horizon in stats['horizons']:
                h_stats = stats['horizons'][horizon]
                h_name = horizon_names[horizon]
                
                logger.info(f"\n📊 {h_name}")
                logger.info(f"  Señales evaluadas:    {h_stats['count']}")
                logger.info(f"  Ganadoras:            {h_stats['winners']} ({h_stats['win_rate']:.1f}%)")
                logger.info(f"  Perdedoras:           {h_stats['losers']} ({100-h_stats['win_rate']:.1f}%)")
                logger.info(f"  Retorno promedio:     {h_stats['avg_return']:+.2f}%")
                logger.info(f"  Retorno máximo:       {h_stats['max_return']:+.2f}%")
                logger.info(f"  Retorno mínimo:       {h_stats['min_return']:+.2f}%")
                
                if h_stats['winners'] > 0:
                    logger.info(f"  Promedio ganadoras:   {h_stats['positive_avg']:+.2f}%")
                if h_stats['losers'] > 0:
                    logger.info(f"  Promedio perdedoras:  {h_stats['negative_avg']:+.2f}%")
        
        # Top 10 mejores y peores (actual)
        if 'current' in stats['horizons']:
            logger.info("\n" + "=" * 60)
            logger.info("TOP 10 MEJORES SEÑALES (Retorno Actual)")
            logger.info("=" * 60)
            
            sorted_results = sorted(
                [r for r in self.results if 'current' in r],
                key=lambda x: x['current']['return_pct'],
                reverse=True
            )
            
            for i, result in enumerate(sorted_results[:10], 1):
                ticker = result['ticker']
                entry = result['entry_date']
                ret = result['current']['return_pct']
                days = result['current']['days_held']
                logger.info(f"{i:2d}. {ticker:6s} ({entry}): {ret:+7.2f}% en {days} días")
            
            logger.info("\n" + "=" * 60)
            logger.info("TOP 10 PEORES SEÑALES (Retorno Actual)")
            logger.info("=" * 60)
            
            for i, result in enumerate(sorted_results[-10:][::-1], 1):
                ticker = result['ticker']
                entry = result['entry_date']
                ret = result['current']['return_pct']
                days = result['current']['days_held']
                logger.info(f"{i:2d}. {ticker:6s} ({entry}): {ret:+7.2f}% en {days} días")
        
        # Conclusiones
        logger.info("\n" + "=" * 60)
        logger.info("CONCLUSIONES")
        logger.info("=" * 60)
        
        if 'current' in stats['horizons']:
            current = stats['horizons']['current']
            
            if current['win_rate'] > 60:
                logger.info(f"✅ Win rate de {current['win_rate']:.1f}% - Sistema EFECTIVO")
            elif current['win_rate'] > 50:
                logger.info(f"⚠️  Win rate de {current['win_rate']:.1f}% - Sistema MARGINAL")
            else:
                logger.info(f"❌ Win rate de {current['win_rate']:.1f}% - Sistema INEFECTIVO")
            
            if current['avg_return'] > 5:
                logger.info(f"✅ Retorno promedio {current['avg_return']:+.2f}% - BUENO")
            elif current['avg_return'] > 0:
                logger.info(f"⚠️  Retorno promedio {current['avg_return']:+.2f}% - MODERADO")
            else:
                logger.info(f"❌ Retorno promedio {current['avg_return']:+.2f}% - NEGATIVO")


def main():
    """Función principal"""
    
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info("BACKTESTING SISTEMA WEINSTEIN")
    logger.info("=" * 60)
    logger.info(f"Fecha: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Crear instancia de backtest
        backtest = WeinsteinBacktest(db)
        
        # Ejecutar backtest de señales BUY
        results = backtest.run_backtest(signal_type='BUY')
        
        if not results:
            logger.error("No se generaron resultados")
            sys.exit(1)
        
        # Calcular estadísticas
        stats = backtest.calculate_statistics()
        
        # Imprimir reporte
        backtest.print_report(stats)
        
        # Duración
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info(f"Duración: {duration:.1f} segundos")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error crítico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
