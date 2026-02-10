"""Paper trading API endpoints."""

from fastapi import APIRouter, Request, HTTPException

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


@router.get("/paper_trades")
async def get_all_trades(request: Request):
    svc = request.app.state.paper_trading_service
    return await svc.get_all_trades()
