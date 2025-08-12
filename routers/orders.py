from datetime import datetime

from fastapi import APIRouter, HTTPException
from starlette import status
from starlette.responses import RedirectResponse, JSONResponse

import crud
import dependencies
import models
import schemas
from exceptions import SomethingWentWrongError

router = APIRouter()


@router.get("/orders/list/", response_model=schemas.OrdersPaginatedSchema)
async def order_list_endpoint(
        db: dependencies.DpGetDB,
        user: dependencies.GetCurrentUser,
        offset: int = 0,
        limit: int = 20
) -> schemas.OrdersPaginatedSchema:

    order_list = await crud.order_list(db=db, user_profile=user.user_profile)
    if not order_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orders were not found")
    if not isinstance(order_list, dict):
        raise SomethingWentWrongError

    return schemas.OrdersPaginatedSchema(
        items=order_list.get("all_orders"),
        offset=offset,
        limit=limit,
        total_items=order_list.get("total_items")
    )

