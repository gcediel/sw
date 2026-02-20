#!/usr/bin/env python3
"""
Script para actualización diaria de datos
Se ejecuta automáticamente vía cron cada día

Uso:
    python scripts/daily_update.py
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from app.database import SessionLocal, Stock, DailyData, Position
from app.data_collector import DataCollector
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import requests
import logging
from datetime import datetime
from sqlalchemy import desc

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/stanweinstein/daily_update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _send_telegram(text: str):
    """Enviar mensaje a Telegram (best effort)"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }, timeout=10)
    except Exception as e:
        logger.warning(f"⚠ Error enviando Telegram: {e}")


def check_stop_losses(db):
    """Alertar vía Telegram cuando el precio diario cae bajo el stop loss de una posición abierta"""
    positions = db.query(Position).filter(Position.status == 'OPEN').all()
    if not positions:
        return

    alerts = []
    for pos in positions:
        latest = db.query(DailyData).filter(
            DailyData.stock_id == pos.stock_id
        ).order_by(desc(DailyData.date)).first()

        if not latest:
            continue

        current_price = float(latest.close)
        stop_loss = float(pos.stop_loss)

        if current_price <= stop_loss:
            dist_pct = (current_price - stop_loss) / stop_loss * 100
            alerts.append({
                'ticker': pos.stock.ticker,
                'current_price': current_price,
                'stop_loss': stop_loss,
                'dist_pct': dist_pct,
                'entry_date': pos.entry_date,
                'entry_price': float(pos.entry_price),
            })
            logger.warning(
                f"🚨 STOP LOSS activado: {pos.stock.ticker} | "
                f"Precio: {current_price:.2f} | Stop: {stop_loss:.2f} | "
                f"Dist: {dist_pct:.1f}%"
            )

    if alerts:
        msg = "🚨 <b>ALERTAS STOP LOSS</b>\n\n"
        for a in alerts:
            msg += (
                f"<b>{a['ticker']}</b>\n"
                f"  Precio: {a['current_price']:.2f} | Stop: {a['stop_loss']:.2f}\n"
                f"  Distancia: {a['dist_pct']:.1f}%\n"
                f"  Entrada: {a['entry_date']} @ {a['entry_price']:.2f}\n\n"
            )
        _send_telegram(msg)
        logger.info(f"✓ {len(alerts)} alerta(s) de stop loss enviadas a Telegram")


def main():
    """Función principal de actualización diaria"""
    start_time = datetime.now()
    
    logger.info("=" * 60)
    logger.info(f"ACTUALIZACIÓN DIARIA - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Obtener todas las acciones activas
        stocks = db.query(Stock).filter(Stock.active == True).all()
        
        if not stocks:
            logger.warning("⚠ No hay acciones activas para actualizar")
            return
        
        total = len(stocks)
        logger.info(f"📈 Acciones a actualizar: {total}")
        logger.info("-" * 60)
        
        collector = DataCollector(db)
        success = 0
        failed = []
        
        # Actualizar cada acción
        for idx, stock in enumerate(stocks, 1):
            ticker = stock.ticker
            logger.info(f"[{idx}/{total}] Actualizando {ticker}...")
            
            try:
                # Actualizar últimos 5 días (cubre fines de semana y festivos)
                if collector.update_daily_data(ticker, days_back=5):
                    success += 1
                else:
                    failed.append(ticker)
                    logger.warning(f"⚠ {ticker}: sin nuevos datos")
            except Exception as e:
                logger.error(f"✗ Error actualizando {ticker}: {e}")
                failed.append(ticker)
        
        # Resumen
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN ACTUALIZACIÓN DIARIA")
        logger.info("=" * 60)
        logger.info(f"Total:             {total}")
        logger.info(f"Actualizadas:      {success} ({success/total*100:.1f}%)")
        logger.info(f"Con errores:       {len(failed)} ({len(failed)/total*100:.1f}%)")
        logger.info(f"Duración:          {duration:.0f} segundos")
        
        if failed:
            logger.warning(f"\n⚠ Tickers con problemas ({len(failed)}):")
            for ticker in failed:
                logger.warning(f"  - {ticker}")

        # Verificar stop losses de la cartera
        logger.info("\n" + "-" * 60)
        logger.info("Verificando stop losses de cartera...")
        try:
            check_stop_losses(db)
        except Exception as e_sl:
            logger.error(f"⚠ Error verificando stop losses: {e_sl}")

        logger.info("=" * 60)
        logger.info("ACTUALIZACIÓN DIARIA COMPLETADA")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ Error crítico en actualización diaria: {e}")
        sys.exit(1)
    finally:
        db.close()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
