#!/usr/bin/env python3
"""
Sistema Weinstein - API REST con FastAPI
Dashboard web para visualización de análisis y señales

Uso:
    uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import and_, func, desc

from app.database import SessionLocal, Stock, WeeklyData, Signal, DailyData
from app.analyzer import WeinsteinAnalyzer
from app.signals import SignalGenerator

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema Weinstein",
    description="Dashboard de análisis técnico basado en metodología Stan Weinstein",
    version="0.3.0"
)

# Montar archivos estáticos y templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")


# ============================================
# UTILIDADES
# ============================================

def get_db():
    """Obtener sesión de base de datos"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================
# PÁGINAS HTML
# ============================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Página principal - Dashboard"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "base_path": "/sw"
    })


@app.get("/stocks", response_class=HTMLResponse)
async def stocks_page(request: Request):
    """Página de lista de acciones"""
    return templates.TemplateResponse("stocks.html", {
        "request": request,
        "base_path": "/sw"
    })


@app.get("/stock/{ticker}", response_class=HTMLResponse)
async def stock_detail_page(request: Request, ticker: str):
    """Página de detalle de acción"""
    return templates.TemplateResponse("stock_detail.html", {
        "request": request,
        "ticker": ticker.upper(),
        "base_path": "/sw"
    })


@app.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    """Página de señales"""
    return templates.TemplateResponse("signals.html", {
        "request": request,
        "base_path": "/sw"
    })


@app.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request):
    """Página de watchlist (Etapa 2)"""
    return templates.TemplateResponse("watchlist.html", {
        "request": request,
        "base_path": "/sw"
    })


# ============================================
# API ENDPOINTS - DASHBOARD
# ============================================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """
    Obtener estadísticas para el dashboard
    
    Returns:
        - Total acciones
        - Distribución por etapas
        - Señales última semana
        - Última actualización
    """
    db = SessionLocal()
    
    try:
        # Total acciones activas
        total_stocks = db.query(Stock).filter(Stock.active == True).count()
        
        # Distribución por etapas (última semana de cada acción)
        subq = db.query(
            WeeklyData.stock_id,
            func.max(WeeklyData.week_end_date).label('max_date')
        ).group_by(WeeklyData.stock_id).subquery()
        
        stage_distribution = db.query(
            WeeklyData.stage,
            func.count(WeeklyData.stage).label('count')
        ).join(
            subq,
            and_(
                WeeklyData.stock_id == subq.c.stock_id,
                WeeklyData.week_end_date == subq.c.max_date
            )
        ).group_by(WeeklyData.stage).all()
        
        # Formatear distribución
        stages = {
            1: {'name': 'Base/Consolidación', 'count': 0, 'color': '#6c757d'},
            2: {'name': 'Tendencia Alcista', 'count': 0, 'color': '#28a745'},
            3: {'name': 'Techo/Distribución', 'count': 0, 'color': '#ffc107'},
            4: {'name': 'Tendencia Bajista', 'count': 0, 'color': '#dc3545'}
        }
        
        for stage, count in stage_distribution:
            if stage in stages:
                stages[stage]['count'] = count
        
        # Señales última semana
        one_week_ago = datetime.now().date() - timedelta(days=7)
        signals_last_week = db.query(Signal).filter(
            Signal.signal_date >= one_week_ago
        ).all()
        
        signals_count = {
            'BUY': sum(1 for s in signals_last_week if s.signal_type == 'BUY'),
            'SELL': sum(1 for s in signals_last_week if s.signal_type == 'SELL'),
            'STAGE_CHANGE': sum(1 for s in signals_last_week if s.signal_type == 'STAGE_CHANGE')
        }
        
        # Última actualización
        last_update = db.query(func.max(DailyData.date)).scalar()
        
        return {
            'total_stocks': total_stocks,
            'stages': stages,
            'signals_last_week': signals_count,
            'last_update': last_update.isoformat() if last_update else None
        }
        
    finally:
        db.close()


# ============================================
# API ENDPOINTS - ACCIONES
# ============================================

@app.get("/api/stocks")
async def get_stocks(
    stage: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Obtener lista de acciones con filtros
    
    Args:
        stage: Filtrar por etapa (1, 2, 3, 4)
        search: Buscar por ticker o nombre
        limit: Número máximo de resultados
        offset: Desplazamiento para paginación
    """
    db = SessionLocal()
    
    try:
        # Subconsulta para última semana
        subq = db.query(
            WeeklyData.stock_id,
            func.max(WeeklyData.week_end_date).label('max_date')
        ).group_by(WeeklyData.stock_id).subquery()
        
        # Query base
        query = db.query(Stock, WeeklyData).join(
            WeeklyData, Stock.id == WeeklyData.stock_id
        ).join(
            subq,
            and_(
                WeeklyData.stock_id == subq.c.stock_id,
                WeeklyData.week_end_date == subq.c.max_date
            )
        ).filter(Stock.active == True)
        
        # Filtros
        if stage is not None:
            query = query.filter(WeeklyData.stage == stage)
        
        if search:
            search_term = f"%{search.upper()}%"
            query = query.filter(
                (Stock.ticker.like(search_term)) | 
                (Stock.name.like(search_term))
            )
        
        # Ordenar por pendiente MA30 descendente (más fuertes primero)
        query = query.order_by(desc(WeeklyData.ma30_slope))
        
        # Paginación
        total = query.count()
        results = query.offset(offset).limit(limit).all()
        
        # Formatear resultados
        stocks = []
        for stock, weekly in results:
            stocks.append({
                'ticker': stock.ticker,
                'name': stock.name,
                'exchange': stock.exchange,
                'stage': weekly.stage,
                'price': float(weekly.close),
                'ma30': float(weekly.ma30) if weekly.ma30 else None,
                'ma30_slope': float(weekly.ma30_slope) if weekly.ma30_slope else None,
                'week_end_date': weekly.week_end_date.isoformat(),
                'distance_from_ma30': ((float(weekly.close) - float(weekly.ma30)) / float(weekly.ma30) * 100) if weekly.ma30 else None
            })
        
        return {
            'total': total,
            'limit': limit,
            'offset': offset,
            'stocks': stocks
        }
        
    finally:
        db.close()


@app.get("/api/stock/{ticker}")
async def get_stock_detail(ticker: str):
    """
    Obtener detalle completo de una acción
    
    Args:
        ticker: Símbolo de la acción (ej: AAPL)
    """
    db = SessionLocal()
    
    try:
        ticker = ticker.upper()
        
        # Obtener acción
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        
        if not stock:
            return JSONResponse(
                status_code=404,
                content={'error': f'Acción {ticker} no encontrada'}
            )
        
        # Última semana
        latest_week = db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock.id
        ).order_by(desc(WeeklyData.week_end_date)).first()
        
        if not latest_week:
            return JSONResponse(
                status_code=404,
                content={'error': f'No hay datos semanales para {ticker}'}
            )
        
        # Historial últimas 30 semanas
        history = db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock.id
        ).order_by(desc(WeeklyData.week_end_date)).limit(30).all()
        
        history.reverse()  # Orden cronológico
        
        # Señales de esta acción
        signals = db.query(Signal).filter(
            Signal.stock_id == stock.id
        ).order_by(desc(Signal.signal_date)).limit(10).all()
        
        return {
            'ticker': stock.ticker,
            'name': stock.name,
            'exchange': stock.exchange,
            'current': {
                'stage': latest_week.stage,
                'price': float(latest_week.close),
                'ma30': float(latest_week.ma30) if latest_week.ma30 else None,
                'ma30_slope': float(latest_week.ma30_slope) if latest_week.ma30_slope else None,
                'week_end_date': latest_week.week_end_date.isoformat(),
                'distance_from_ma30': ((float(latest_week.close) - float(latest_week.ma30)) / float(latest_week.ma30) * 100) if latest_week.ma30 else None
            },
            'history': [
                {
                    'week_end_date': w.week_end_date.isoformat(),
                    'close': float(w.close),
                    'ma30': float(w.ma30) if w.ma30 else None,
                    'stage': w.stage
                }
                for w in history
            ],
            'signals': [
                {
                    'date': s.signal_date.isoformat(),
                    'type': s.signal_type,
                    'stage_from': s.stage_from,
                    'stage_to': s.stage_to,
                    'price': float(s.price)
                }
                for s in signals
            ]
        }
        
    finally:
        db.close()


# ============================================
# API ENDPOINTS - SEÑALES
# ============================================

@app.get("/api/signals")
async def get_signals(
    signal_type: Optional[str] = None,
    days: int = 30,
    limit: int = 50
):
    """
    Obtener señales recientes
    
    Args:
        signal_type: Filtrar por tipo (BUY, SELL, STAGE_CHANGE)
        days: Días hacia atrás
        limit: Número máximo de resultados
    """
    db = SessionLocal()
    
    try:
        # Query base
        cutoff_date = datetime.now().date() - timedelta(days=days)
        
        query = db.query(Signal, Stock).join(
            Stock, Signal.stock_id == Stock.id
        ).filter(Signal.signal_date >= cutoff_date)
        
        # Filtro por tipo
        if signal_type:
            query = query.filter(Signal.signal_type == signal_type.upper())
        
        # Ordenar por fecha descendente
        query = query.order_by(desc(Signal.signal_date))
        
        # Limitar
        results = query.limit(limit).all()
        
        # Formatear
        signals = []
        for signal, stock in results:
            signals.append({
                'ticker': stock.ticker,
                'name': stock.name,
                'date': signal.signal_date.isoformat(),
                'type': signal.signal_type,
                'stage_from': signal.stage_from,
                'stage_to': signal.stage_to,
                'price': float(signal.price),
                'ma30': float(signal.ma30) if signal.ma30 else None
            })
        
        return {
            'total': len(signals),
            'signals': signals
        }
        
    finally:
        db.close()


# ============================================
# API ENDPOINTS - WATCHLIST (Etapa 2)
# ============================================

@app.get("/api/watchlist")
async def get_watchlist():
    """
    Obtener acciones en Etapa 2 (tendencia alcista)
    Ordenadas por fuerza (pendiente MA30)
    """
    db = SessionLocal()
    
    try:
        analyzer = WeinsteinAnalyzer(db)
        stocks = analyzer.get_stocks_by_stage(2)
        
        # Ordenar por pendiente (más fuerte primero)
        stocks_sorted = sorted(
            stocks,
            key=lambda x: x['slope'] or 0,
            reverse=True
        )
        
        return {
            'total': len(stocks_sorted),
            'stocks': stocks_sorted
        }
        
    finally:
        db.close()


# ============================================
# HEALTH CHECK
# ============================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'version': '0.3.0',
        'timestamp': datetime.now().isoformat()
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
