#!/usr/bin/env python3
"""
Regenera las señales BUY recientes aplicando los filtros actuales de signals.py.

Uso:
    python scripts/regenerate_buy_signals.py            # últimas 2 semanas
    python scripts/regenerate_buy_signals.py --weeks 4  # últimas 4 semanas
    python scripts/regenerate_buy_signals.py --dry-run  # solo muestra, no modifica

El script:
  1. Muestra las señales BUY existentes en el período
  2. Las elimina
  3. Regenera con los filtros actuales (volumen + MRS)
  4. Muestra las nuevas señales generadas
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from datetime import datetime, timedelta
from sqlalchemy import and_
from app.database import SessionLocal, Signal, Stock
from app.signals import SignalGenerator


def run(weeks_back: int = 2, dry_run: bool = False):
    db = SessionLocal()

    cutoff = datetime.now().date() - timedelta(weeks=weeks_back)

    print("=" * 60)
    print("REGENERACIÓN DE SEÑALES BUY")
    print(f"Período:   últimas {weeks_back} semanas (desde {cutoff})")
    print(f"Modo:      {'SIMULACIÓN (sin cambios)' if dry_run else 'REAL'}")
    print("=" * 60)

    # --- Señales BUY actuales en el período ---
    existing = (
        db.query(Signal, Stock)
        .join(Stock, Signal.stock_id == Stock.id)
        .filter(
            Signal.signal_type == 'BUY',
            Signal.signal_date >= cutoff,
        )
        .order_by(Signal.signal_date.desc())
        .all()
    )

    print(f"\nSeñales BUY existentes ({len(existing)}):")
    for sig, stock in existing:
        notif = " [notificada]" if sig.notified else ""
        print(f"  {stock.ticker:8s}  {sig.signal_date}  ${float(sig.price):.2f}{notif}")

    if not existing:
        print("  (ninguna)")

    if dry_run:
        print("\n[dry-run] No se realizan cambios.")
        db.close()
        return

    # --- Eliminar señales BUY del período ---
    ids_to_delete = [sig.id for sig, _ in existing]
    if ids_to_delete:
        db.query(Signal).filter(Signal.id.in_(ids_to_delete)).delete(synchronize_session=False)
        db.commit()
        print(f"\n✓ Eliminadas {len(ids_to_delete)} señales BUY")
    else:
        print("\n(No había señales que eliminar)")

    # --- Regenerar con filtros actuales ---
    print(f"\nRegenerando señales (últimas {weeks_back} semanas)...")
    generator = SignalGenerator(db)
    result = generator.generate_signals_for_all_stocks(weeks_back=weeks_back)
    db.commit()

    print(f"✓ Señales generadas: {result['total_signals']} "
          f"en {result['stocks_with_signals']} acciones")
    if result['failed']:
        print(f"  (errores en {result['failed']} acciones)")

    # --- Mostrar nuevas señales BUY ---
    new_signals = (
        db.query(Signal, Stock)
        .join(Stock, Signal.stock_id == Stock.id)
        .filter(
            Signal.signal_type == 'BUY',
            Signal.signal_date >= cutoff,
        )
        .order_by(Signal.signal_date.desc())
        .all()
    )

    print(f"\nNuevas señales BUY ({len(new_signals)}):")
    for sig, stock in new_signals:
        dist = (float(sig.price) - float(sig.ma30)) / float(sig.ma30) * 100 if sig.ma30 else 0
        print(f"  {stock.ticker:8s}  {sig.signal_date}  "
              f"${float(sig.price):.2f}  dist_MA30:{dist:+.1f}%  {stock.name or ''}")

    print(f"\nResumen: {len(existing)} señales → {len(new_signals)} señales "
          f"({len(existing) - len(new_signals):+d} filtradas)")
    print("=" * 60)

    db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Regenera señales BUY con filtros actuales')
    parser.add_argument('--weeks', type=int, default=2,
                        help='Semanas hacia atrás a regenerar (default: 2)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Solo muestra las señales actuales, sin modificar')
    args = parser.parse_args()
    run(args.weeks, args.dry_run)
