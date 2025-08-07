from fastapi import APIRouter

router = APIRouter()

@router.get("/movies")
async def movies_list():
    return {"message": "All Movies"}