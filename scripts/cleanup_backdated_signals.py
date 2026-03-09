#!/usr/bin/env python3
"""
Limpieza de señales con fecha retroactiva (backdated).

Muestra y elimina señales con signal_date entre RANGE_FROM y RANGE_TO.
Rango por defecto: 22 feb – 5 mar 2026 (señales anteriores al último viernes
que fueron generadas/enviadas por error en la ejecución del 7-8 mar 2026).

Uso:
    python scripts/cleanup_backdated_signals.py          # dry-run: solo muestra
    python scripts/cleanup_backdated_signals.py --delete  # elimina realmente
"""
import sys
sys.path.insert(0, '/home/stanweinstein')
sys.path.insert(0, '/home/gcb/Desarrollo/stanweinstein_test')

import argparse
from datetime import date
from app.database import SessionLocal, Signal, Stock

# Rango de signal_date a limpiar (señales retroactivas)
RANGE_FROM = date(2026, 2, 22)  # 14 días antes del último viernes
RANGE_TO   = date(2026, 3, 5)   # día anterior al último viernes (6 mar)


def main(dry_run: bool):
    db = SessionLocal()
    try:
        # Primero mostrar TODAS las señales recientes para diagnóstico
        all_recent = (
            db.query(Signal, Stock)
            .join(Stock, Signal.stock_id == Stock.id)
            .filter(Signal.signal_date >= date(2026, 2, 1))
            .order_by(Signal.signal_date.asc())
            .all()
        )

        print(f"=== Señales en BD desde 1 feb 2026 ({len(all_recent)} total) ===")
        print(f"{'Fecha señal':<14} {'Creada':<22} {'Ticker':<8} {'Tipo':<12} {'Precio':>8}")
        print("-" * 70)
        for signal, stock in all_recent:
            marker = " ← RETROACTIVA" if RANGE_FROM <= signal.signal_date <= RANGE_TO else ""
            print(
                f"{str(signal.signal_date):<14} "
                f"{str(signal.created_at)[:19]:<22} "
                f"{stock.ticker:<8} "
                f"{signal.signal_type:<12} "
                f"${float(signal.price):>7.2f}{marker}"
            )

        # Filtrar las retroactivas
        rows = [
            (s, st) for s, st in all_recent
            if RANGE_FROM <= s.signal_date <= RANGE_TO
        ]

        print(f"\n=== Señales a eliminar: {len(rows)} ===")
        if not rows:
            print("Ninguna. Nada que limpiar.")
            return

        if dry_run:
            print("Dry-run: no se eliminó nada. Ejecuta con --delete para confirmar.")
            return

        ids = [s.id for s, _ in rows]
        deleted = db.query(Signal).filter(Signal.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        print(f"✓ {deleted} señales eliminadas correctamente.")

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
