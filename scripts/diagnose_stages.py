#!/usr/bin/env python3
"""
Diagnóstico de detección de etapas Weinstein
Analiza patrones de transición y distribución de etapas en weekly_data

Uso:
    python scripts/diagnose_stages.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from app.database import SessionLocal, Stock, WeeklyData
from sqlalchemy import and_, func


def run_diagnostics():
    db = SessionLocal()

    print("=" * 65)
    print("DIAGNÓSTICO DE ETAPAS WEINSTEIN")
    print("=" * 65)

    # ----------------------------------------------------------------
    # 1. Distribución global de etapas (última semana por acción)
    # ----------------------------------------------------------------
    print("\n1. DISTRIBUCIÓN DE ETAPAS (semana más reciente por acción)")
    print("-" * 65)

    subq = db.query(
        WeeklyData.stock_id,
        func.max(WeeklyData.week_end_date).label('max_date')
    ).group_by(WeeklyData.stock_id).subquery()

    latest = db.query(WeeklyData).join(
        subq,
        and_(
            WeeklyData.stock_id == subq.c.stock_id,
            WeeklyData.week_end_date == subq.c.max_date
        )
    ).all()

    stage_counts = defaultdict(int)
    null_stage = 0
    for w in latest:
        if w.stage is None:
            null_stage += 1
        else:
            stage_counts[w.stage] += 1

    total = len(latest)
    print(f"  Total acciones con weekly_data: {total}")
    for stage in [1, 2, 3, 4]:
        n = stage_counts[stage]
        print(f"  Etapa {stage}: {n:4d}  ({n/total*100:.1f}%)")
    if null_stage:
        print(f"  NULL:    {null_stage:4d}  ({null_stage/total*100:.1f}%) ← sin MA30 suficiente")

    # ----------------------------------------------------------------
    # 2. Análisis de duración de cada etapa
    # ----------------------------------------------------------------
    print("\n2. DURACIÓN MEDIA DE CADA ETAPA (semanas consecutivas)")
    print("-" * 65)

    stocks = db.query(Stock).filter(Stock.active == True).all()
    stage_durations = defaultdict(list)

    for stock in stocks:
        weekly = db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock.id,
                WeeklyData.stage.isnot(None)
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()

        if not weekly:
            continue

        current_stage = weekly[0].stage
        run_len = 1
        for i in range(1, len(weekly)):
            if weekly[i].stage == current_stage:
                run_len += 1
            else:
                stage_durations[current_stage].append(run_len)
                current_stage = weekly[i].stage
                run_len = 1
        stage_durations[current_stage].append(run_len)

    for stage in [1, 2, 3, 4]:
        durations = stage_durations[stage]
        if durations:
            avg  = sum(durations) / len(durations)
            med  = sorted(durations)[len(durations) // 2]
            mn   = min(durations)
            mx   = max(durations)
            d1   = sum(1 for d in durations if d == 1)
            d2   = sum(1 for d in durations if d == 2)
            print(f"  Etapa {stage}: avg={avg:.1f}w  mediana={med}w  "
                  f"min={mn}w  max={mx}w  | 1sem={d1}  2sem={d2}")

    # ----------------------------------------------------------------
    # 3. Ciclos rápidos: 1→2→3 en ≤ 3 semanas
    # ----------------------------------------------------------------
    print("\n3. CICLOS RÁPIDOS: 1→2→3 en ≤ 3 semanas")
    print("-" * 65)

    fast_cycles = []
    slow_stage2 = []  # Stage 2 que dura ≥ 4 semanas

    for stock in stocks:
        weekly = db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock.id,
                WeeklyData.stage.isnot(None)
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()

        if len(weekly) < 3:
            continue

        i = 0
        while i < len(weekly) - 1:
            if weekly[i].stage == 1 and weekly[i+1].stage == 2:
                # Encontrada transición 1→2, medir duración en 2
                start_2 = i + 1
                j = start_2 + 1
                while j < len(weekly) and weekly[j].stage == 2:
                    j += 1
                duration_2 = j - start_2  # semanas en etapa 2

                if duration_2 <= 3:
                    next_stage = weekly[j].stage if j < len(weekly) else None
                    fast_cycles.append({
                        'ticker': stock.ticker,
                        'entry_week': weekly[start_2].week_end_date,
                        'duration_2': duration_2,
                        'next_stage': next_stage,
                        'slope_entry': float(weekly[start_2].ma30_slope or 0),
                    })
                else:
                    slow_stage2.append({
                        'ticker': stock.ticker,
                        'entry_week': weekly[start_2].week_end_date,
                        'duration_2': duration_2,
                    })
                i = j
            else:
                i += 1

    print(f"  Ciclos rápidos (Etapa 2 ≤ 3 sem): {len(fast_cycles)}")
    print(f"  Etapa 2 sostenida  (≥ 4 sem):     {len(slow_stage2)}")
    if fast_cycles + slow_stage2:
        total_e2 = len(fast_cycles) + len(slow_stage2)
        print(f"  % señales falsas (rápidas):        {len(fast_cycles)/total_e2*100:.1f}%")

    if fast_cycles:
        print(f"\n  Ejemplos de ciclos rápidos:")
        for c in sorted(fast_cycles, key=lambda x: x['duration_2'])[:15]:
            print(f"    {c['ticker']:8s}  {c['entry_week']}  "
                  f"dur={c['duration_2']}sem  slope_entrada={c['slope_entry']:+.4f}  "
                  f"→Etapa {c['next_stage']}")

    # ----------------------------------------------------------------
    # 4. Distribución de slopes cuando se detecta Stage 2
    # ----------------------------------------------------------------
    print("\n4. DISTRIBUCIÓN DE MA30_SLOPE EN INICIO DE ETAPA 2")
    print("-" * 65)

    entry_slopes = []
    for stock in stocks:
        weekly = db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock.id,
                WeeklyData.stage.isnot(None),
                WeeklyData.ma30_slope.isnot(None)
            )
        ).order_by(WeeklyData.week_end_date.asc()).all()

        for i in range(1, len(weekly)):
            if weekly[i-1].stage != 2 and weekly[i].stage == 2:
                entry_slopes.append(float(weekly[i].ma30_slope))

    if entry_slopes:
        entry_slopes.sort()
        n = len(entry_slopes)
        pct = lambda p: entry_slopes[int(n * p / 100)]
        print(f"  N entradas a Etapa 2: {n}")
        print(f"  Slope mínimo:         {min(entry_slopes):+.4f}  ({min(entry_slopes)*100:+.2f}%)")
        print(f"  Percentil 10:         {pct(10):+.4f}  ({pct(10)*100:+.2f}%)")
        print(f"  Percentil 25:         {pct(25):+.4f}  ({pct(25)*100:+.2f}%)")
        print(f"  Mediana:              {pct(50):+.4f}  ({pct(50)*100:+.2f}%)")
        print(f"  Percentil 75:         {pct(75):+.4f}  ({pct(75)*100:+.2f}%)")
        print(f"  Slope máximo:         {max(entry_slopes):+.4f}  ({max(entry_slopes)*100:+.2f}%)")

        # Cuántas entradas tienen slope apenas por encima del umbral (1.5%)
        marginal = sum(1 for s in entry_slopes if 0.015 <= s <= 0.025)
        print(f"\n  Entradas con slope 'marginal' (1.5–2.5%): {marginal} ({marginal/n*100:.1f}%)")
        strong = sum(1 for s in entry_slopes if s > 0.03)
        print(f"  Entradas con slope 'fuerte'   (>3.0%):   {strong} ({strong/n*100:.1f}%)")

    # ----------------------------------------------------------------
    # 5. Distribución de slopes en semanas de Etapa 2 en curso
    # ----------------------------------------------------------------
    print("\n5. SLOPE DURANTE ETAPA 2 (todas las semanas, no solo entrada)")
    print("-" * 65)

    stage2_slopes = []
    for stock in stocks:
        weekly = db.query(WeeklyData).filter(
            and_(
                WeeklyData.stock_id == stock.id,
                WeeklyData.stage == 2,
                WeeklyData.ma30_slope.isnot(None)
            )
        ).all()
        stage2_slopes.extend(float(w.ma30_slope) for w in weekly)

    if stage2_slopes:
        stage2_slopes.sort()
        n = len(stage2_slopes)
        neg = sum(1 for s in stage2_slopes if s < 0)
        marginal = sum(1 for s in stage2_slopes if 0 <= s < 0.015)
        print(f"  Semanas en Etapa 2 con slope negativo (<0):   {neg} ({neg/n*100:.1f}%)")
        print(f"  Semanas en Etapa 2 con slope 0–1.5%:          {marginal} ({marginal/n*100:.1f}%)")
        print(f"  (Estas deberían haberse reclasificado ya como Etapa 3)")

    db.close()
    print("\n" + "=" * 65)


if __name__ == '__main__':
    run_diagnostics()
