#!/usr/bin/env python3
"""
Sistema Weinstein - API REST con FastAPI
Dashboard web para visualización de análisis y señales

Uso:
    uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
"""
import sys
sys.path.insert(0, '/home/stanweinstein')

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List
from datetime import datetime, timedelta, date as date_type
from sqlalchemy import and_, func, desc

from app.database import SessionLocal, Stock, WeeklyData, Signal, DailyData, Position
from app.analyzer import WeinsteinAnalyzer
from app.signals import SignalGenerator
from app.auth import verify_password, save_password

# Base path: "/sw" en producción (detrás de proxy), "" en local
import os
BASE_PATH = os.environ.get("BASE_PATH", "")

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema Weinstein",
    description="Dashboard de análisis técnico basado en metodología Stan Weinstein",
    version="0.3.0"
)

# ============================================
# AUTENTICACIÓN - Middleware
# ============================================

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Permitir rutas públicas
        if path == "/login" or path.startswith("/static"):
            return await call_next(request)
        # Verificar sesión
        if not request.session.get("authenticated"):
            return RedirectResponse(url=f"{BASE_PATH}/login", status_code=302)
        return await call_next(request)

# Orden: AuthMiddleware se añade después → se ejecuta después de SessionMiddleware
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key="weinstein-session-secret-k3y-2024")

# Montar archivos estáticos y templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de login"""
    if request.session.get("authenticated"):
        return RedirectResponse(url=f"{BASE_PATH}/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "base_path": BASE_PATH,
        "error": None
    })


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, password: str = Form(...)):
    """Procesar login"""
    if verify_password(password):
        request.session["authenticated"] = True
        return RedirectResponse(url=f"{BASE_PATH}/", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "base_path": BASE_PATH,
        "error": "Contraseña incorrecta"
    })


@app.get("/logout")
async def logout(request: Request):
    """Cerrar sesión"""
    request.session.clear()
    return RedirectResponse(url=f"{BASE_PATH}/login", status_code=302)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Página de administración"""
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "base_path": BASE_PATH,
        "success": None,
        "error": None
    })


@app.post("/admin/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Cambiar contraseña"""
    if not verify_password(current_password):
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "base_path": BASE_PATH,
            "error": "La contraseña actual es incorrecta",
            "success": None
        })

    if new_password != confirm_password:
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "base_path": BASE_PATH,
            "error": "Las contraseñas nuevas no coinciden",
            "success": None
        })

    if len(new_password) < 4:
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "base_path": BASE_PATH,
            "error": "La contraseña debe tener al menos 4 caracteres",
            "success": None
        })

    save_password(new_password)
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "base_path": BASE_PATH,
        "success": "Contraseña cambiada correctamente",
        "error": None
    })


# ============================================
# API ENDPOINTS - ADMIN STOCKS CRUD
# ============================================

class StockCreate(BaseModel):
    ticker: str
    name: str = ""
    exchange: str = ""

class StockUpdate(BaseModel):
    name: str = None
    exchange: str = None
    active: bool = None


def detect_exchange(ticker: str) -> str:
    """Detectar mercado a partir del sufijo del ticker"""
    if "." in ticker:
        suffix = ticker.split(".")[-1].upper()
        if suffix == "MC":
            return "BME"
        return suffix
    return "NASDAQ"


@app.get("/api/admin/stocks")
async def api_admin_stocks():
    """Lista todas las acciones (activas e inactivas)"""
    db = SessionLocal()
    try:
        stocks = db.query(Stock).order_by(Stock.ticker).all()
        return {
            "stocks": [
                {
                    "id": s.id,
                    "ticker": s.ticker,
                    "name": s.name or "",
                    "exchange": s.exchange or "",
                    "active": s.active,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in stocks
            ]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.post("/api/admin/stocks")
async def api_admin_stock_create(data: StockCreate):
    """Crear nueva accion"""
    db = SessionLocal()
    try:
        ticker = data.ticker.strip().upper()
        if not ticker:
            return JSONResponse(status_code=400, content={"error": "El ticker es obligatorio"})

        existing = db.query(Stock).filter(Stock.ticker == ticker).first()
        if existing:
            return JSONResponse(status_code=400, content={"error": f"El ticker {ticker} ya existe"})

        exchange = data.exchange.strip() if data.exchange.strip() else detect_exchange(ticker)
        stock = Stock(
            ticker=ticker,
            name=data.name.strip() or ticker,
            exchange=exchange,
            active=True,
        )
        db.add(stock)
        db.commit()
        db.refresh(stock)

        return {
            "id": stock.id,
            "ticker": stock.ticker,
            "name": stock.name,
            "exchange": stock.exchange,
            "active": stock.active,
        }
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.put("/api/admin/stocks/{stock_id}")
async def api_admin_stock_update(stock_id: int, data: StockUpdate):
    """Editar accion existente"""
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            return JSONResponse(status_code=404, content={"error": "Accion no encontrada"})

        if data.name is not None:
            stock.name = data.name.strip()
        if data.exchange is not None:
            stock.exchange = data.exchange.strip()
        if data.active is not None:
            stock.active = data.active

        db.commit()
        return {
            "id": stock.id,
            "ticker": stock.ticker,
            "name": stock.name,
            "exchange": stock.exchange,
            "active": stock.active,
        }
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.delete("/api/admin/stocks/{stock_id}")
async def api_admin_stock_delete(stock_id: int):
    """Eliminar accion y todos sus datos historicos"""
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            return JSONResponse(status_code=404, content={"error": "Accion no encontrada"})

        ticker = stock.ticker
        db.delete(stock)
        db.commit()
        return {"message": f"Accion {ticker} eliminada correctamente"}
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


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
        "base_path": BASE_PATH
    })


@app.get("/stocks", response_class=HTMLResponse)
async def stocks_page(request: Request):
    """Página de lista de acciones"""
    return templates.TemplateResponse("stocks.html", {
        "request": request,
        "base_path": BASE_PATH
    })


@app.get("/stock/{ticker}", response_class=HTMLResponse)
async def stock_detail_page(request: Request, ticker: str):
    """Página de detalle de acción"""
    return templates.TemplateResponse("stock_detail.html", {
        "request": request,
        "ticker": ticker.upper(),
        "base_path": BASE_PATH
    })


@app.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    """Página de señales"""
    return templates.TemplateResponse("signals.html", {
        "request": request,
        "base_path": BASE_PATH
    })


@app.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request):
    """Página de watchlist (Etapa 2)"""
    return templates.TemplateResponse("watchlist.html", {
        "request": request,
        "base_path": BASE_PATH
    })


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    """Página de cartera de posiciones"""
    return templates.TemplateResponse("portfolio.html", {
        "request": request,
        "base_path": BASE_PATH
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

        # Acciones no actualizadas - DIARIO
        last_daily_date = last_update  # ya calculado arriba
        if last_daily_date:
            daily_subq = db.query(
                DailyData.stock_id,
                func.max(DailyData.date).label('max_date')
            ).join(Stock).filter(Stock.active == True).group_by(DailyData.stock_id).subquery()

            outdated_daily = db.query(func.count()).select_from(daily_subq).filter(
                daily_subq.c.max_date < last_daily_date
            ).scalar()
        else:
            outdated_daily = 0

        # Acciones no actualizadas - SEMANAL
        last_weekly_date = db.query(func.max(WeeklyData.week_end_date)).scalar()
        if last_weekly_date:
            weekly_subq = db.query(
                WeeklyData.stock_id,
                func.max(WeeklyData.week_end_date).label('max_date')
            ).join(Stock).filter(Stock.active == True).group_by(WeeklyData.stock_id).subquery()

            outdated_weekly = db.query(func.count()).select_from(weekly_subq).filter(
                weekly_subq.c.max_date < last_weekly_date
            ).scalar()
        else:
            outdated_weekly = 0

        return {
            'total_stocks': total_stocks,
            'stages': stages,
            'signals_last_week': signals_count,
            'last_update': last_update.isoformat() if last_update else None,
            'outdated_daily': outdated_daily,
            'outdated_weekly': outdated_weekly,
            'last_daily_date': str(last_daily_date) if last_daily_date else None,
            'last_weekly_date': str(last_weekly_date) if last_weekly_date else None,
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

        # Historial últimas 104 semanas (2 años)
        history = db.query(WeeklyData).filter(
            WeeklyData.stock_id == stock.id
        ).order_by(desc(WeeklyData.week_end_date)).limit(104).all()

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
                    'open': float(w.open) if w.open else None,
                    'high': float(w.high) if w.high else None,
                    'low': float(w.low) if w.low else None,
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
# API ENDPOINTS - PORTFOLIO (CARTERA)
# ============================================

class PositionCreate(BaseModel):
    ticker: str
    entry_date: str        # ISO date "2026-02-20"
    entry_price: float
    quantity: float
    stop_loss: float
    notes: str = ""

class PositionUpdate(BaseModel):
    stop_loss: float = None
    notes: str = None

class PositionClose(BaseModel):
    exit_date: str
    exit_price: float


def _position_with_pnl(pos: Position, current_price: float) -> dict:
    """Serializar posición con cálculo de P&L"""
    entry_price = float(pos.entry_price)
    quantity = float(pos.quantity)
    stop_loss = float(pos.stop_loss)
    invested = entry_price * quantity
    pnl_eur = (current_price - entry_price) * quantity
    pnl_pct = (current_price - entry_price) / entry_price * 100
    dist_stop_pct = (current_price - stop_loss) / stop_loss * 100
    return {
        "id": pos.id,
        "ticker": pos.stock.ticker,
        "name": pos.stock.name,
        "entry_date": pos.entry_date.isoformat(),
        "entry_price": entry_price,
        "quantity": quantity,
        "current_price": current_price,
        "stop_loss": stop_loss,
        "invested": round(invested, 2),
        "pnl_eur": round(pnl_eur, 2),
        "pnl_pct": round(pnl_pct, 2),
        "dist_stop_pct": round(dist_stop_pct, 2),
        "stop_triggered": current_price <= stop_loss,
        "notes": pos.notes or "",
        "status": pos.status,
    }


def _position_closed_dict(pos: Position) -> dict:
    """Serializar posición cerrada"""
    entry_price = float(pos.entry_price)
    exit_price = float(pos.exit_price)
    quantity = float(pos.quantity)
    pnl_eur = (exit_price - entry_price) * quantity
    pnl_pct = (exit_price - entry_price) / entry_price * 100
    return {
        "id": pos.id,
        "ticker": pos.stock.ticker,
        "name": pos.stock.name,
        "entry_date": pos.entry_date.isoformat(),
        "exit_date": pos.exit_date.isoformat() if pos.exit_date else None,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
        "invested": round(entry_price * quantity, 2),
        "pnl_eur": round(pnl_eur, 2),
        "pnl_pct": round(pnl_pct, 2),
        "notes": pos.notes or "",
    }


def _get_current_price(db, stock_id: int) -> float:
    """Obtener último precio diario disponible de un stock"""
    latest = db.query(DailyData).filter(
        DailyData.stock_id == stock_id
    ).order_by(desc(DailyData.date)).first()
    if latest:
        return float(latest.close)
    # fallback a precio semanal
    latest_w = db.query(WeeklyData).filter(
        WeeklyData.stock_id == stock_id
    ).order_by(desc(WeeklyData.week_end_date)).first()
    if latest_w:
        return float(latest_w.close)
    return 0.0


@app.get("/api/portfolio")
async def api_portfolio_open():
    """Posiciones abiertas con P&L actual"""
    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.status == 'OPEN'
        ).order_by(Position.entry_date.desc()).all()

        result = []
        for pos in positions:
            current_price = _get_current_price(db, pos.stock_id)
            result.append(_position_with_pnl(pos, current_price))
        return {"positions": result, "total": len(result)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.post("/api/portfolio")
async def api_portfolio_create(data: PositionCreate):
    """Abrir nueva posición (compra)"""
    db = SessionLocal()
    try:
        ticker = data.ticker.strip().upper()
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        if not stock:
            return JSONResponse(status_code=404, content={"error": f"Ticker {ticker} no encontrado"})

        try:
            entry_date = date_type.fromisoformat(data.entry_date)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Formato de fecha inválido (usar YYYY-MM-DD)"})

        if data.entry_price <= 0 or data.quantity <= 0 or data.stop_loss <= 0:
            return JSONResponse(status_code=400, content={"error": "Precio, cantidad y stop loss deben ser positivos"})

        pos = Position(
            stock_id=stock.id,
            entry_date=entry_date,
            entry_price=data.entry_price,
            quantity=data.quantity,
            stop_loss=data.stop_loss,
            notes=data.notes,
            status='OPEN',
        )
        db.add(pos)
        db.commit()
        db.refresh(pos)

        current_price = _get_current_price(db, stock.id)
        return _position_with_pnl(pos, current_price)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.put("/api/portfolio/{position_id}")
async def api_portfolio_update(position_id: int, data: PositionUpdate):
    """Actualizar stop loss y/o notas"""
    db = SessionLocal()
    try:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return JSONResponse(status_code=404, content={"error": "Posición no encontrada"})
        if pos.status != 'OPEN':
            return JSONResponse(status_code=400, content={"error": "Solo se pueden editar posiciones abiertas"})

        if data.stop_loss is not None:
            if data.stop_loss <= 0:
                return JSONResponse(status_code=400, content={"error": "El stop loss debe ser positivo"})
            pos.stop_loss = data.stop_loss
        if data.notes is not None:
            pos.notes = data.notes

        db.commit()
        current_price = _get_current_price(db, pos.stock_id)
        return _position_with_pnl(pos, current_price)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.post("/api/portfolio/{position_id}/close")
async def api_portfolio_close(position_id: int, data: PositionClose):
    """Cerrar posición (venta)"""
    db = SessionLocal()
    try:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return JSONResponse(status_code=404, content={"error": "Posición no encontrada"})
        if pos.status != 'OPEN':
            return JSONResponse(status_code=400, content={"error": "La posición ya está cerrada"})

        try:
            exit_date = date_type.fromisoformat(data.exit_date)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Formato de fecha inválido (usar YYYY-MM-DD)"})

        if data.exit_price <= 0:
            return JSONResponse(status_code=400, content={"error": "El precio de salida debe ser positivo"})

        pos.exit_date = exit_date
        pos.exit_price = data.exit_price
        pos.status = 'CLOSED'
        db.commit()
        return _position_closed_dict(pos)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.get("/api/portfolio/history")
async def api_portfolio_history():
    """Historial de posiciones cerradas"""
    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.status == 'CLOSED'
        ).order_by(Position.exit_date.desc()).all()

        result = [_position_closed_dict(p) for p in positions]
        total_pnl = sum(p["pnl_eur"] for p in result)
        return {"positions": result, "total": len(result), "total_pnl": round(total_pnl, 2)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.get("/api/portfolio/summary")
async def api_portfolio_summary():
    """Estadísticas globales del portfolio"""
    db = SessionLocal()
    try:
        open_positions = db.query(Position).filter(Position.status == 'OPEN').all()

        total_invested = 0.0
        total_pnl = 0.0
        pnl_pcts = []

        for pos in open_positions:
            current_price = _get_current_price(db, pos.stock_id)
            entry_price = float(pos.entry_price)
            quantity = float(pos.quantity)
            invested = entry_price * quantity
            pnl_eur = (current_price - entry_price) * quantity
            pnl_pct = (current_price - entry_price) / entry_price * 100
            total_invested += invested
            total_pnl += pnl_eur
            pnl_pcts.append(pnl_pct)

        avg_pnl_pct = sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0.0

        return {
            "open_count": len(open_positions),
            "total_invested": round(total_invested, 2),
            "total_pnl_eur": round(total_pnl, 2),
            "avg_pnl_pct": round(avg_pnl_pct, 2),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.delete("/api/portfolio/history")
async def api_portfolio_clear_history():
    """Borrar todo el historial de posiciones cerradas"""
    db = SessionLocal()
    try:
        deleted = db.query(Position).filter(Position.status == 'CLOSED').delete()
        db.commit()
        return {"message": f"Historial borrado: {deleted} posiciones eliminadas"}
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
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
