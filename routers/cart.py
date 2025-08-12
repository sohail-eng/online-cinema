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
