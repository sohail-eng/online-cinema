from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
async def users_list():
    return {"message": "All Users"}
