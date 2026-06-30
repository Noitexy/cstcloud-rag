from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.models.schemas import EvalRequest, EvalResponse
from app.services.eval_service import EvalService

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.post("/single", response_model=EvalResponse)
async def evaluate(payload: EvalRequest, db: Session = Depends(get_db)):
    return await EvalService().evaluate(db, payload)
