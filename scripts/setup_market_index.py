#!/usr/bin/env python3
"""
Añade SPY (S&P 500 ETF) a la base de datos como índice de referencia de mercado.
Carga histórico diario, agrega a semanal y calcula etapas.

Uso:
    python scripts/setup_market_index.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, date, timedelta
import pandas as pd

from app.database import SessionLocal, Stock, DailyData, WeeklyData
from app.aggregator import WeeklyAggregator
from app.analyzer import WeinsteinAnalyzer
from sqlalchemy import and_

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def insert_spy(db):
    """Inserta SPY en la tabla stocks si no existe."""
    spy = db.query(Stock).filter(Stock.ticker == 'SPY').first()
    if spy:
        logger.info(f"SPY ya existe en BD (id={spy.id})")
        return spy

    spy = Stock(
        ticker='SPY',
        name='SPDR S&P 500 ETF Trust',
        exchange='INDEX',
        active=True
    )
    db.add(spy)
    db.commit()
    db.refresh(spy)
    logger.info(f"✓ SPY insertado (id={spy.id})")
    return spy


def load_spy_daily(db, spy_id, years_back=3):
    """Descarga datos diarios de SPY con TwelveData e inserta en daily_data."""
    import requests
    from app.config import TWELVEDATA_API_KEY

    start_date = (datetime.now() - timedelta(days=365 * years_back)).strftime('%Y-%m-%d')

    logger.info(f"Descargando SPY vía TwelveData desde {start_date}...")

    url = "https://api.twelvedata.com/time_series"
    params = {
        'symbol': 'SPY',
        'interval': '1day',
        'outputsize': 5000,   # máximo para obtener todo el histórico de una vez
        'start_date': start_date,
        'apikey': TWELVEDATA_API_KEY,
        'format': 'JSON',
        'order': 'ASC'
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
    except Exception as e:
        logger.error(f"Error en petición TwelveData: {e}")
        return 0

    if 'values' not in data:
        logger.error(f"TwelveData no devolvió datos: {data.get('message', data)}")
        return 0

    values = data['values']
    logger.info(f"  Filas recibidas: {len(values)}")

    # Obtener fechas ya existentes
    existing = set(
        r[0] for r in db.query(DailyData.date)
        .filter(DailyData.stock_id == spy_id).all()
    )

    inserted = 0
    for v in values:
        row_date = pd.to_datetime(v['datetime']).date()
        if row_date in existing:
            continue
        record = DailyData(
            stock_id=spy_id,
            date=row_date,
            open=float(v['open']),
            high=float(v['high']),
            low=float(v['low']),
            close=float(v['close']),
            volume=int(v['volume']) if v.get('volume') else None
        )
        db.add(record)
        inserted += 1

    db.commit()
    logger.info(f"✓ {inserted} días de SPY insertados en daily_data")
    return inserted


def aggregate_spy_weekly(db, spy_id):
    """Agrega datos diarios de SPY a weekly_data y calcula MA30."""
    logger.info("Agregando SPY a datos semanales (histórico completo)...")
    aggregator = WeeklyAggregator(db)
    # weeks_back=160 cubre ~3 años de histórico
    weeks = aggregator.aggregate_stock_weekly_data(spy_id, weeks_back=160)
    logger.info(f"✓ {weeks} semanas agregadas para SPY")
    return weeks


def analyze_spy_stages(db, spy_id):
    """Calcula etapas Weinstein para SPY."""
    logger.info("Calculando etapas Weinstein para SPY (histórico completo)...")
    analyzer = WeinsteinAnalyzer(db)
    # weeks_back=160 cubre todo el histórico disponible
    processed = analyzer.analyze_stock_stages(spy_id, weeks_back=160)
    logger.info(f"✓ {processed} semanas analizadas para SPY")
    return processed


def print_spy_summary(db, spy_id):
    """Muestra resumen de los últimos 10 datos semanales de SPY."""
    weekly = db.query(WeeklyData).filter(
        WeeklyData.stock_id == spy_id
    ).order_by(WeeklyData.week_end_date.desc()).limit(10).all()

    print("\n" + "="*65)
    print("RESUMEN SPY — Últimas 10 semanas")
    print("="*65)
    print(f"{'Semana':12s}  {'Close':8s}  {'MA30':8s}  {'Slope':8s}  {'Stage':6s}")
    print("-"*65)
    for w in reversed(weekly):
        ma30  = float(w.ma30)  if w.ma30  else 0
        slope = float(w.ma30_slope) if w.ma30_slope else 0
        close = float(w.close)
        print(f"{str(w.week_end_date):12s}  {close:8.2f}  {ma30:8.2f}  "
              f"{slope*100:+7.2f}%  {str(w.stage):6s}")
    print("="*65)

    # Etapa actual
    if weekly:
        current = weekly[0]
        stage_names = {1: 'Base/Acumulación', 2: 'Avance alcista',
                       3: 'Techo/Distribución', 4: 'Declive bajista'}
        stage_name = stage_names.get(current.stage, 'Desconocida')
        print(f"\n  SPY hoy → Etapa {current.stage}: {stage_name}")


def main():
    db = SessionLocal()
    try:
        print("="*65)
        print("CONFIGURACIÓN ÍNDICE DE MERCADO (SPY)")
        print("="*65)

        spy = insert_spy(db)
        load_spy_daily(db, spy.id, years_back=3)
        aggregate_spy_weekly(db, spy.id)
        analyze_spy_stages(db, spy.id)
        print_spy_summary(db, spy.id)

        print("\n✓ SPY configurado correctamente.")
        print("  Puedes usarlo como filtro de mercado en el backtest.\n")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
