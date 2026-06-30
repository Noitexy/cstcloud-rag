from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.db import ModelConfig, get_db
from app.models.schemas import ConfigResponse, ConfigUpdate

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
def get_config(db: Session = Depends(get_db)) -> ModelConfig:
    return db.get(ModelConfig, 1)


@router.post("", response_model=ConfigResponse)
def update_config(payload: ConfigUpdate, db: Session = Depends(get_db)) -> ModelConfig:
    config = db.get(ModelConfig, 1)
    for key, value in payload.model_dump().items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config
