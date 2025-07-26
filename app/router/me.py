from __future__ import annotations

from typing import Literal

from app.database import (
    User as DBUser,
)
from app.dependencies import get_current_user
from app.models.user import (
    APIMe,
)
from app.utils import convert_db_user_to_api_user

from .api_router import router

from fastapi import Depends


@router.get("/me/{ruleset}", response_model=APIMe)
@router.get("/me/", response_model=APIMe)
async def get_user_info_default(
    ruleset: Literal["osu", "taiko", "fruits", "mania"] = "osu",
    current_user: DBUser = Depends(get_current_user),
):
    """获取当前用户信息（默认使用osu模式）"""
    # 默认使用osu模式
    api_user = await convert_db_user_to_api_user(current_user, ruleset)

    # Convert User to APIMe
    api_me = APIMe(**api_user.model_dump())
    return api_me
