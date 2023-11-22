from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, Depends
from starlette.exceptions import HTTPException

from lnbits.core.models import User
from lnbits.decorators import check_admin

users_router = APIRouter(prefix="/users/api/v1", dependencies=[Depends(check_admin)])


@users_router.get("/user/")
async def api_get_users(
    user: User = Depends(check_admin),
) -> Optional[list[dict[str, str]]]:
    # admin_settings = await get_u(user.super_user)
    try:
        return [
            {
                "usr": user.id,
            }
        ]
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Could not fetch users.",
        )


@users_router.delete("/user/", status_code=HTTPStatus.OK)
async def api_delete_user() -> None:
    pass
