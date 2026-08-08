from fastapi import APIRouter

router = APIRouter(prefix="/experience", tags=["Experience"])


@router.get("/")
async def get_experience():
    return "hello"
