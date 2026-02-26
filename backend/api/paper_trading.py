"""Paper trading API endpoints."""

from fastapi import APIRouter, Request, HTTPException, Query

from models.paper_trade import OpenTradeRequest, CloseTradeRequest

router = APIRouter()


@router.post("/paper_trades/open")
async def open_trade(request: Request, body: OpenTradeRequest):
    svc = request.app.state.paper_trading_service
    try:
        trade = await svc.open_trade(body)
        return trade.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/paper_trades/close")
async def close_trade(request: Request, body: CloseTradeRequest):
    svc = request.app.state.paper_trading_service
    try:
        trade = await svc.close_trade(body)
        return trade.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/paper_positions")
async def get_positions(request: Request):
    svc = request.app.state.paper_trading_service
    positions = await svc.get_open_positions()
    return [p.model_dump(mode="json") for p in positions]


@router.get("/paper_portfolio/summary")
async def get_portfolio_summary(request: Request):
    svc = request.app.state.paper_trading_service
    summary = await svc.get_portfolio_summary()
    return summary.model_dump(mode="json")


@router.get("/paper_portfolio/equity_curve")
async def get_equity_curve(
    request: Request,
    flip_sides: bool = Query(False, description="Flip YES/NO to simulate betting against Trump"),
):
    svc = request.app.state.paper_trading_service
    result = await svc.get_equity_curve(flip_sides=flip_sides)
    return result.model_dump(mode="json")


@router.get("/paper_portfolio/equity_curve_dual")
async def get_equity_curve_dual(request: Request):
    """Returns both pro-Trump and anti-Trump equity curves from a single ES fetch."""
    svc = request.app.state.paper_trading_service
    return await svc.get_equity_curve_dual()


@router.get("/monte_carlo")
async def get_monte_carlo(
    request: Request,
    iterations: int = Query(10000, ge=100, le=100000, description="Number of simulation iterations"),
):
    """Monte Carlo simulation: sample 70/80/90% of tracked markets N times.

    Returns distribution of total portfolio P&L to answer:
    'What would happen if only X% of events existed?'
    """
    svc = request.app.state.paper_trading_service
    result = await svc.run_monte_carlo(iterations=iterations)
    return result.model_dump(mode="json")


@router.get("/paper_trades")
async def get_all_trades(request: Request):
    svc = request.app.state.paper_trading_service
    return await svc.get_all_trades()
