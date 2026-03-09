#!/usr/bin/env python3
"""
Limpieza de señales con fecha retroactiva (backdated).

Elimina señales que fueron creadas durante la ejecución del 7-8 mar 2026
pero con signal_date anterior al viernes 6 mar 2026 (el viernes real de esa semana).

Uso:
    python scripts/cleanup_backdated_signals.py          # modo dry-run (solo muestra)
    python scripts/cleanup_backdated_signals.py --delete  # elimina realmente
"""
import sys
sys.path.insert(0, '/home/stanweinstein')
sys.path.insert(0, '/home/gcb/Desarrollo/stanweinstein_test')

import argparse
from datetime import date
from app.database import SessionLocal, Signal, Stock

# Señales creadas en la ejecución problemática (sábado/domingo 7-8 mar)
# con signal_date anterior al último viernes (6 mar)
CREATED_FROM = date(2026, 3, 7)   # fecha desde la que se consideran "de esa ejecución"
LAST_FRIDAY  = date(2026, 3, 6)   # único signal_date válido para esa semana


def main(dry_run: bool):
    db = SessionLocal()
    try:
        # Obtener señales a eliminar
        rows = (
            db.query(Signal, Stock)
            .join(Stock, Signal.stock_id == Stock.id)
            .filter(
                Signal.created_at >= CREATED_FROM,
                Signal.signal_date < LAST_FRIDAY
            )
            .order_by(Signal.signal_date.asc())
            .all()
        )

        if not rows:
            print("No se encontraron señales retroactivas. Nada que limpiar.")
            return

        print(f"{'MODO DRY-RUN — ' if dry_run else ''}Señales a eliminar: {len(rows)}\n")
        print(f"{'Fecha señal':<14} {'Creada':<22} {'Ticker':<8} {'Tipo':<12} {'Precio':>8}")
        print("-" * 70)
        for signal, stock in rows:
            print(
                f"{str(signal.signal_date):<14} "
                f"{str(signal.created_at)[:19]:<22} "
                f"{stock.ticker:<8} "
                f"{signal.signal_type:<12} "
                f"${float(signal.price):>7.2f}"
            )

        if dry_run:
            print(f"\nDry-run: no se eliminó nada. Ejecuta con --delete para confirmar.")
            return

        # Eliminar
        ids = [s.id for s, _ in rows]
        deleted = db.query(Signal).filter(Signal.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        print(f"\n✓ {deleted} señales eliminadas correctamente.")

    except Exception as e:
        db.rollback()
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--delete', action='store_true', help='Eliminar realmente (sin --delete es dry-run)')
    args = parser.parse_args()
    main(dry_run=not args.delete)
