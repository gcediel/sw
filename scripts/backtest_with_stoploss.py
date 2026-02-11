#!/usr/bin/env python3
"""
Backtesting Weinstein con STOP LOSS
Simula operaciones reales con gestión de riesgo según metodología Weinstein

Reglas de Stop Loss Weinstein:
1. Stop Loss Inicial: 8% por debajo del precio de entrada (configurable)
2. Trailing Stop: Se mueve hacia arriba cuando el precio sube
3. Salida si el precio rompe MA30 a la baja
4. Salida si cambia a Etapa 3 o 4

Uso:
    python scripts/backtest_with_stoploss.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from datetime import datetime, timedelta
from app.database import SessionLocal, Stock, Signal, DailyData, WeeklyData
from sqlalchemy import and_
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/backtest_stoploss.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WeinsteinBacktestWithStopLoss:
    """Backtesting con Stop Loss según metodología Weinstein"""
    
    def __init__(self, db, initial_stop_pct: float = 8.0, trailing_stop_pct: float = 15.0):
        """
        Args:
            initial_stop_pct: Stop loss inicial en % (default 8%)
            trailing_stop_pct: Trailing stop en % desde máximo (default 15%)
        """
        self.db = db
        self.initial_stop_pct = initial_stop_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.results = []
    
    def get_daily_prices_after_entry(self, stock_id: int, entry_date, days: int = 400):
        """
        Obtener precios diarios después de la entrada
        """
        end_date = entry_date + timedelta(days=days)
        
        prices = self.db.query(DailyData).filter(
            and_(
                DailyData.stock_id == stock_id,
                DailyData.date > entry_date,
                DailyData.date <= end_date
            )
        ).order_by(DailyData.date.asc()).all()
        
        return prices
    
    def get_weekly_data_after_entry(self, stock_id: int, entry_date):
        """
        Obtener datos semanales después de la entrada
        Para detectar cambios de etapa
        """
        weekly = self.db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock_id,
                WeeklyData.week_end_date > entry_date
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()
        
        return weekly
    
    def simulate_trade_with_stops(self, signal):
        """
        Simular una operación completa con stops
        
        Returns:
            dict con resultado de la operación
        """
        stock = self.db.query(Stock).filter(Stock.id == signal.stock_id).first()
        
        if not stock:
            return None
        
        entry_price = float(signal.price)
        entry_date = signal.signal_date
        
        # Stop loss inicial (X% por debajo)
        initial_stop = entry_price * (1 - self.initial_stop_pct / 100)
        
        # Variables de tracking
        highest_price = entry_price
        trailing_stop = initial_stop
        current_stop = initial_stop
        
        exit_reason = None
        exit_date = None
        exit_price = None
        
        # Obtener precios diarios y semanales
        daily_prices = self.get_daily_prices_after_entry(signal.stock_id, entry_date)
        weekly_data = self.get_weekly_data_after_entry(signal.stock_id, entry_date)
        
        # Crear dict de etapas semanales para búsqueda rápida
        weekly_stages = {}
        for week in weekly_data:
            weekly_stages[week.week_end_date] = {
                'stage': week.stage,
                'ma30': float(week.ma30) if week.ma30 else None,
                'close': float(week.close)
            }
        
        # Simular día a día
        for day in daily_prices:
            price = float(day.close)
            low = float(day.low)
            date = day.date
            
            # Actualizar máximo histórico
            if price > highest_price:
                highest_price = price
                
                # Actualizar trailing stop (X% desde máximo)
                trailing_stop = highest_price * (1 - self.trailing_stop_pct / 100)
                
                # El stop siempre sube, nunca baja
                if trailing_stop > current_stop:
                    current_stop = trailing_stop
            
            # REGLA 1: Stop Loss alcanzado (el mínimo del día toca el stop)
            if low <= current_stop:
                exit_reason = 'STOP_LOSS'
                exit_date = date
                exit_price = current_stop  # Ejecuta al precio del stop
                break
            
            # REGLA 2: Cambio de etapa a 3 o 4 (verificar datos semanales)
            # Buscar la última semana disponible hasta esta fecha
            last_week_date = None
            for week_date in sorted(weekly_stages.keys()):
                if week_date <= date:
                    last_week_date = week_date
            
            if last_week_date and last_week_date in weekly_stages:
                week_info = weekly_stages[last_week_date]
                
                # Si cambia a Etapa 3 o 4, salir
                if week_info['stage'] in [3, 4]:
                    exit_reason = f"STAGE_CHANGE_TO_{week_info['stage']}"
                    exit_date = date
                    exit_price = price
                    break
                
                # REGLA 3: Precio cierra por debajo de MA30 en semanal
                if week_info['ma30'] and week_info['close'] < week_info['ma30']:
                    exit_reason = 'BELOW_MA30'
                    exit_date = date
                    exit_price = price
                    break
        
        # Si no se activó ninguna salida, mantener hasta hoy
        if not exit_date:
            if daily_prices:
                last_day = daily_prices[-1]
                exit_reason = 'HOLD'
                exit_date = last_day.date
                exit_price = float(last_day.close)
            else:
                return None
        
        # Calcular retornos
        absolute_return = exit_price - entry_price
        percent_return = (absolute_return / entry_price) * 100
        days_held = (exit_date - entry_date).days
        
        return {
            'ticker': stock.ticker,
            'name': stock.name,
            'entry_date': entry_date,
            'entry_price': entry_price,
            'initial_stop': initial_stop,
            'exit_date': exit_date,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'highest_price': highest_price,
            'final_stop': current_stop,
            'days_held': days_held,
            'return_pct': percent_return,
            'return_abs': absolute_return,
            'winner': percent_return > 0
        }
    
    def run_backtest(self, signal_type: str = 'BUY'):
        """Ejecutar backtest con stop loss"""
        
        logger.info("=" * 60)
        logger.info(f"BACKTESTING CON STOP LOSS - Señales {signal_type}")
        logger.info("=" * 60)
        logger.info(f"Stop Loss Inicial:  {self.initial_stop_pct}%")
        logger.info(f"Trailing Stop:      {self.trailing_stop_pct}%")
        logger.info("=" * 60)
        
        # Obtener señales
        signals = self.db.query(Signal).filter(
            Signal.signal_type == signal_type
        ).order_by(Signal.signal_date.asc()).all()
        
        if not signals:
            logger.warning(f"No hay señales de tipo {signal_type}")
            return None
        
        logger.info(f"\nTotal señales {signal_type}: {len(signals)}\n")
        
        # Procesar cada señal
        for idx, signal in enumerate(signals, 1):
            logger.info(f"[{idx}/{len(signals)}] Simulando operación...")
            
            result = self.simulate_trade_with_stops(signal)
            
            if result:
                self.results.append(result)
                
                # Log básico
                ticker = result['ticker']
                ret = result['return_pct']
                reason = result['exit_reason']
                days = result['days_held']
                
                logger.info(f"  {ticker}: {ret:+.2f}% en {days}d (salida: {reason})")
        
        return self.results
    
    def calculate_statistics(self):
        """Calcular estadísticas del backtest con stops"""
        
        if not self.results:
            return None
        
        returns = [r['return_pct'] for r in self.results]
        winners = [r for r in self.results if r['winner']]
        losers = [r for r in self.results if not r['winner']]
        
        # Contar razones de salida
        exit_reasons = {}
        for r in self.results:
            reason = r['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        stats = {
            'total_trades': len(self.results),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': (len(winners) / len(self.results)) * 100 if self.results else 0,
            'avg_return': sum(returns) / len(returns) if returns else 0,
            'max_return': max(returns) if returns else 0,
            'min_return': min(returns) if returns else 0,
            'avg_winner': sum([r['return_pct'] for r in winners]) / len(winners) if winners else 0,
            'avg_loser': sum([r['return_pct'] for r in losers]) / len(losers) if losers else 0,
            'avg_days_held': sum([r['days_held'] for r in self.results]) / len(self.results),
            'exit_reasons': exit_reasons
        }
        
        return stats
    
    def print_detailed_results(self):
        """Imprimir detalle de cada operación"""
        
        logger.info("\n" + "=" * 60)
        logger.info("DETALLE DE CADA OPERACIÓN")
        logger.info("=" * 60)
        
        for idx, r in enumerate(self.results, 1):
            status = "✓ GANADORA" if r['winner'] else "✗ PERDEDORA"
            
            logger.info(f"\n[{idx}/{len(self.results)}] {r['ticker']} - {r['name']} {status}")
            logger.info(f"  Entrada:         {r['entry_date']} @ ${r['entry_price']:.2f}")
            logger.info(f"  Stop inicial:    ${r['initial_stop']:.2f} (-{self.initial_stop_pct}%)")
            logger.info(f"  Precio máximo:   ${r['highest_price']:.2f} (+{((r['highest_price']/r['entry_price'])-1)*100:.2f}%)")
            logger.info(f"  Stop final:      ${r['final_stop']:.2f}")
            logger.info(f"  Salida:          {r['exit_date']} @ ${r['exit_price']:.2f}")
            logger.info(f"  Razón salida:    {r['exit_reason']}")
            logger.info(f"  Días en cartera: {r['days_held']}")
            logger.info(f"  Retorno:         {r['return_pct']:+.2f}%")
    
    def print_summary(self, stats):
        """Imprimir resumen estadístico"""
        
        if not stats:
            return
        
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN DE RESULTADOS")
        logger.info("=" * 60)
        
        logger.info(f"\nTotal operaciones:    {stats['total_trades']}")
        logger.info(f"Ganadoras:            {stats['winners']} ({stats['win_rate']:.1f}%)")
        logger.info(f"Perdedoras:           {stats['losers']} ({100-stats['win_rate']:.1f}%)")
        
        logger.info(f"\nRetornos:")
        logger.info(f"  Promedio total:     {stats['avg_return']:+.2f}%")
        logger.info(f"  Promedio ganadoras: {stats['avg_winner']:+.2f}%")
        logger.info(f"  Promedio perdedoras:{stats['avg_loser']:+.2f}%")
        logger.info(f"  Máximo:             {stats['max_return']:+.2f}%")
        logger.info(f"  Mínimo:             {stats['min_return']:+.2f}%")
        
        logger.info(f"\nTiempo:")
        logger.info(f"  Días promedio:      {stats['avg_days_held']:.0f} días")
        
        logger.info(f"\nRazones de salida:")
        for reason, count in sorted(stats['exit_reasons'].items(), key=lambda x: x[1], reverse=True):
            pct = (count / stats['total_trades']) * 100
            logger.info(f"  {reason:20s}: {count:3d} ({pct:5.1f}%)")
        
        # Top mejores y peores
        logger.info("\n" + "=" * 60)
        logger.info("TOP 5 MEJORES OPERACIONES")
        logger.info("=" * 60)
        
        sorted_results = sorted(self.results, key=lambda x: x['return_pct'], reverse=True)
        for i, r in enumerate(sorted_results[:5], 1):
            logger.info(f"{i}. {r['ticker']:6s} {r['entry_date']} → {r['exit_date']}: {r['return_pct']:+7.2f}% ({r['exit_reason']})")
        
        logger.info("\n" + "=" * 60)
        logger.info("TOP 5 PEORES OPERACIONES")
        logger.info("=" * 60)
        
        for i, r in enumerate(sorted_results[-5:][::-1], 1):
            logger.info(f"{i}. {r['ticker']:6s} {r['entry_date']} → {r['exit_date']}: {r['return_pct']:+7.2f}% ({r['exit_reason']})")
        
        # Conclusiones
        logger.info("\n" + "=" * 60)
        logger.info("CONCLUSIONES")
        logger.info("=" * 60)
        
        if stats['win_rate'] > 60:
            logger.info(f"✅ Win rate {stats['win_rate']:.1f}% - Sistema EFECTIVO con stops")
        elif stats['win_rate'] > 50:
            logger.info(f"⚠️  Win rate {stats['win_rate']:.1f}% - Sistema MARGINAL")
        else:
            logger.info(f"❌ Win rate {stats['win_rate']:.1f}% - Sistema INEFECTIVO")
        
        if stats['avg_return'] > 3:
            logger.info(f"✅ Retorno promedio {stats['avg_return']:+.2f}% - BUENO")
        elif stats['avg_return'] > 0:
            logger.info(f"⚠️  Retorno promedio {stats['avg_return']:+.2f}% - MODERADO")
        else:
            logger.info(f"❌ Retorno promedio {stats['avg_return']:+.2f}% - NEGATIVO")
        
        # Ratio ganancia/pérdida
        if stats['avg_loser'] != 0:
            profit_loss_ratio = abs(stats['avg_winner'] / stats['avg_loser'])
            logger.info(f"\n📊 Ratio Ganancia/Pérdida: {profit_loss_ratio:.2f}:1")
            
            if profit_loss_ratio > 2:
                logger.info("   ✅ Ganadoras compensan ampliamente las perdedoras")
            elif profit_loss_ratio > 1.5:
                logger.info("   ⚠️  Ganadoras compensan las perdedoras")
            else:
                logger.info("   ❌ Ganadoras NO compensan bien las perdedoras")


def main():
    """Función principal"""
    
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info("BACKTESTING WEINSTEIN CON STOP LOSS")
    logger.info("=" * 60)
    logger.info(f"Fecha: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Crear instancia de backtest
        # Stop inicial 8%, trailing stop 15% (valores típicos Weinstein)
        backtest = WeinsteinBacktestWithStopLoss(
            db, 
            initial_stop_pct=8.0,
            trailing_stop_pct=15.0
        )
        
        # Ejecutar backtest
        results = backtest.run_backtest(signal_type='BUY')
        
        if not results:
            logger.error("No se generaron resultados")
            sys.exit(1)
        
        # Calcular estadísticas
        stats = backtest.calculate_statistics()
        
        # Imprimir detalle
        backtest.print_detailed_results()
        
        # Imprimir resumen
        backtest.print_summary(stats)
        
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
