from typing import List

from fastapi import APIRouter, HTTPException
from starlette import status
from starlette.responses import JSONResponse

import crud
import dependencies
import models
import schemas
from exceptions import SomethingWentWrongError, MovieAlreadyIsPurchasedOrInCartError
from models import Cart

router = APIRouter()


@router.post("/cart/add_item/{movie_id}/")
async def cart_add_item_endpoint(
        movie_id: int,
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
) -> JSONResponse:
    try:
        added_item = await crud.cart_add_item(db=db, user_profile=user.user_profile, movie_id=movie_id)
    except MovieAlreadyIsPurchasedOrInCartError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Movie is already purchased or in cart.")

    if not isinstance(added_item, dict):
        raise SomethingWentWrongError

    return JSONResponse(content=f"{added_item.get('detail')}", status_code=status.HTTP_200_OK)

