from __future__ import annotations

from app.database import User as DBUser
from app.database.relationship import Relationship, RelationshipResp, RelationshipType
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user

from .api_router import router

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/friends", tags=["relationship"], response_model=list[RelationshipResp])
@router.get("/blocks", tags=["relationship"], response_model=list[RelationshipResp])
async def get_relationship(
    request: Request,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    relationship_type = (
        RelationshipType.FOLLOW
        if request.url.path.endswith("/friends")
        else RelationshipType.BLOCK
    )
    relationships = await db.exec(
        select(Relationship).where(
            Relationship.user_id == current_user.id,
            Relationship.type == relationship_type,
        )
    )
    return [await RelationshipResp.from_db(db, rel) for rel in relationships.unique()]


class AddFriendResp(BaseModel):
    user_relation: RelationshipResp


@router.post("/friends", tags=["relationship"], response_model=AddFriendResp)
@router.post("/blocks", tags=["relationship"])
async def add_relationship(
    request: Request,
    target: int = Query(),
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    relationship_type = (
        RelationshipType.FOLLOW
        if request.url.path.endswith("/friends")
        else RelationshipType.BLOCK
    )
    if target == current_user.id:
        raise HTTPException(422, "Cannot add relationship to yourself")
    relationship = (
        await db.exec(
            select(Relationship).where(
                Relationship.user_id == current_user.id,
                Relationship.target_id == target,
            )
        )
    ).first()
    if relationship:
        relationship.type = relationship_type
        # 这里原来如何是 block 也会修改为 follow
        # 与 ppy/osu-web 的行为保持一致
    else:
        relationship = Relationship(
            user_id=current_user.id,
            target_id=target,
            type=relationship_type,
        )
        db.add(relationship)
    origin_type = relationship.type
    if origin_type == RelationshipType.BLOCK:
        target_relationship = (
            await db.exec(
                select(Relationship).where(
                    Relationship.user_id == target,
                    Relationship.target_id == current_user.id,
                )
            )
        ).first()
        if target_relationship and target_relationship.type == RelationshipType.FOLLOW:
            await db.delete(target_relationship)
    current_user_id = current_user.id
    await db.commit()
    if origin_type == RelationshipType.FOLLOW:
        relationship = (
            await db.exec(
                select(Relationship).where(
                    Relationship.user_id == current_user_id,
                    Relationship.target_id == target,
                )
            )
        ).first()
        assert relationship, "Relationship should exist after commit"
        return AddFriendResp(
            user_relation=await RelationshipResp.from_db(db, relationship)
        )


@router.delete("/friends/{target}", tags=["relationship"])
@router.delete("/blocks/{target}", tags=["relationship"])
async def delete_relationship(
    request: Request,
    target: int,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    relationship_type = (
        RelationshipType.BLOCK
        if "/blocks/" in request.url.path
        else RelationshipType.FOLLOW
    )
    relationship = (
        await db.exec(
            select(Relationship).where(
                Relationship.user_id == current_user.id,
                Relationship.target_id == target,
            )
        )
    ).first()
    if not relationship:
        raise HTTPException(404, "Relationship not found")
    if relationship.type != relationship_type:
        raise HTTPException(422, "Relationship type mismatch")
    await db.delete(relationship)
    await db.commit()
