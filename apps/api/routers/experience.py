from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from deps.db import Db

router = APIRouter(prefix="/experience", tags=["Experience"])


@router.get("/")
async def get_experience(db: Session = Depends(Db)):
    return "hello"
