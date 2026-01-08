from typing import Annotated, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models.account import Account
from ...services.execution.service import get_execution_service

router = APIRouter(prefix="/api/v1/execution", tags=["Trading"])

@router.get("/status/{account_id}")
async def get_execution_status(
    account_id: Annotated[int, Path(...)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Dict[str, Any]:
    """
    Get execution status and active positions for an account.
    """
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    return {
        "account_id": account.id,
        "name": account.name,
        "is_paper_trading": account.is_paper_trading,
        "status": account.status,
        "positions": [
            {
                "symbol": p.symbol,
                "side": p.side,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "unrealized_pnl": p.unrealized_pnl
            } for p in account.positions if p.status == "open"
        ]
    }

@router.post("/reconcile/{account_id}")
async def trigger_reconciliation(
    account_id: Annotated[int, Path(...)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Dict[str, Any]:
    """
    Trigger manual position reconciliation with the exchange.
    """
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    service = get_execution_service()
    return await service.reconcile_positions(db, account)
