from __future__ import annotations

from app.database import User, UserResp
from app.database.lazer_user import SEARCH_INCLUDED
from app.dependencies.database import get_db
from app.models.score import GameMode

from .api_router import router

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import col


class BatchUserResponse(BaseModel):
    users: list[UserResp]


@router.get("/users", response_model=BatchUserResponse)
@router.get("/users/lookup", response_model=BatchUserResponse)
@router.get("/users/lookup/", response_model=BatchUserResponse)
async def get_users(
    user_ids: list[int] = Query(default_factory=list, alias="ids[]"),
    include_variant_statistics: bool = Query(default=False),  # TODO: future use
    session: AsyncSession = Depends(get_db),
):
    if user_ids:
        searched_users = (
            await session.exec(select(User).limit(50).where(col(User.id).in_(user_ids)))
        ).all()
    else:
        searched_users = (await session.exec(select(User).limit(50))).all()
    return BatchUserResponse(
        users=[
            await UserResp.from_db(
                searched_user,
                session,
                include=SEARCH_INCLUDED,
            )
            for searched_user in searched_users
        ]
    )


@router.get("/users/{user}/{ruleset}", response_model=UserResp)
@router.get("/users/{user}/", response_model=UserResp)
@router.get("/users/{user}", response_model=UserResp)
async def get_user_info(
    user: str,
    ruleset: GameMode | None = None,
    session: AsyncSession = Depends(get_db),
):
    searched_user = (
        await session.exec(
            select(User).where(
                User.id == int(user)
                if user.isdigit()
                else User.username == user.removeprefix("@")
            )
        )
    ).first()
    if not searched_user:
        raise HTTPException(404, detail="User not found")
    return await UserResp.from_db(
        searched_user,
        session,
        include=SEARCH_INCLUDED,
        ruleset=ruleset,
    )
