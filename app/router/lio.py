"""LIO (Legacy IO) router for osu-server-spectator compatibility."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import col

from app.dependencies.database import Database
from app.utils import utcnow

router = APIRouter(prefix="/_lio", tags=["LIO"])


class RoomCreateRequest(BaseModel):
    """Request model for creating a multiplayer room."""
    name: str
    user_id: int
    password: str | None = None
    match_type: str = "HeadToHead"
    queue_mode: str = "HostOnly"


def verify_request_signature(request: Request, timestamp: str, body: bytes) -> bool:
    """Verify HMAC signature for shared interop requests."""
    # For now, skip signature verification in development
    # In production, you should implement proper HMAC verification
    return True


@router.post("/multiplayer/rooms")
async def create_multiplayer_room(
    request: Request,
    room_data: dict[str, Any],
    db: Database,
    timestamp: str = "",
) -> dict[str, Any]:
    """Create a new multiplayer room."""
    try:
        # Verify request signature
        body = await request.body()
        if not verify_request_signature(request, timestamp, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature"
            )

        # Parse room data
        if isinstance(room_data, str):
            room_data = json.loads(room_data)

        # Extract required fields
        host_user_id = room_data.get("user_id")
        room_name = room_data.get("name", "Unnamed Room")
        password = room_data.get("password")
        match_type = room_data.get("match_type", "HeadToHead")
        queue_mode = room_data.get("queue_mode", "HostOnly")

        if not host_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing user_id"
            )

        # Verify that the host user exists
        from app.database.lazer_user import User
        from sqlmodel import select
        
        user_result = await db.execute(
            select(User).where(User.id == host_user_id)
        )
        host_user = user_result.first()
        
        if not host_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {host_user_id} not found"
            )

        # Create room in database using SQLModel
        from app.database.room import Room
        from app.models.room import MatchType, QueueMode, RoomStatus
        
        # Convert string values to enums
        try:
            match_type_enum = MatchType(match_type.lower())
        except ValueError:
            match_type_enum = MatchType.HEAD_TO_HEAD
            
        try:
            queue_mode_enum = QueueMode(queue_mode.lower())
        except ValueError:
            queue_mode_enum = QueueMode.HOST_ONLY

        # Create new room
        room = Room(
            name=room_name,
            host_id=host_user_id,
            password=password if password else None,
            type=match_type_enum,
            queue_mode=queue_mode_enum,
            status=RoomStatus.IDLE,
            participant_count=1,
            auto_skip=False,
            auto_start_duration=0,
        )
        
        db.add(room)
        await db.commit()
        await db.refresh(room)
        
        room_id = room.id

        # Add host as participant
        from app.database.room_participated_user import RoomParticipatedUser
        
        participant = RoomParticipatedUser(
            room_id=room_id,
            user_id=host_user_id,
        )
        
        db.add(participant)
        await db.commit()

        return {"room_id": str(room_id)}

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create room: {str(e)}"
        )


@router.put("/multiplayer/rooms/{room_id}/users/{user_id}")
async def add_user_to_room(
    request: Request,
    room_id: int,
    user_id: int,
    db: Database,
    user_data: dict[str, Any] | None = None,
    timestamp: str = "",
) -> dict[str, Any]:
    """Add a user to a multiplayer room."""
    try:
        # Verify request signature
        body = await request.body()
        if not verify_request_signature(request, timestamp, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature"
            )

        from app.database.room import Room
        from sqlmodel import select

        # Check if room exists
        result = await db.execute(
            select(Room.password, Room.participant_count).where(Room.id == room_id)
        )
        room_data = result.first()

        if not room_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        password, participant_count = room_data

        # Check password if room is password protected
        if password and user_data:
            provided_password = user_data.get("password")
            if provided_password != password:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid password"
                )

        # Add user to room (or update existing participation)
        from app.database.room_participated_user import RoomParticipatedUser
        from sqlmodel import select
        
        # Check if user already participated
        existing_participation = await db.execute(
            select(RoomParticipatedUser).where(
                RoomParticipatedUser.room_id == room_id,
                RoomParticipatedUser.user_id == user_id
            )
        )
        existing = existing_participation.first()
        
        if existing:
            # Update existing participation
            existing.left_at = None
            existing.joined_at = utcnow()
        else:
            # Create new participation
            participant = RoomParticipatedUser(
                room_id=room_id,
                user_id=user_id,
            )
            db.add(participant)

        # Update participant count
        active_count = await db.execute(
            select(RoomParticipatedUser).where(
                RoomParticipatedUser.room_id == room_id,
                col(RoomParticipatedUser.left_at).is_(None)
            )
        )
        count = len(active_count.all())
        
        # Update room participant count
        room_update = await db.execute(
            select(Room).where(Room.id == room_id)
        )
        room_obj = room_update.first()
        if room_obj:
            room_obj.participant_count = count

        await db.commit()

        return {"success": True}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add user to room: {str(e)}"
        )


@router.delete("/multiplayer/rooms/{room_id}/users/{user_id}")
async def remove_user_from_room(
    request: Request,
    room_id: int,
    user_id: int,
    db: Database,
    timestamp: str = "",
) -> dict[str, Any]:
    """Remove a user from a multiplayer room."""
    try:
        # Verify request signature
        body = await request.body()
        if not verify_request_signature(request, timestamp, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature"
            )

        from app.database.room import Room
        from app.database.room_participated_user import RoomParticipatedUser
        from sqlmodel import select

        # Remove user from room by setting left_at timestamp
        result = await db.execute(
            select(RoomParticipatedUser).where(
                RoomParticipatedUser.room_id == room_id,
                RoomParticipatedUser.user_id == user_id,
                col(RoomParticipatedUser.left_at).is_(None)
            )
        )
        participation = result.first()
        
        if participation:
            participation.left_at = utcnow()

        # Update participant count
        active_count = await db.execute(
            select(RoomParticipatedUser).where(
                RoomParticipatedUser.room_id == room_id,
                col(RoomParticipatedUser.left_at).is_(None)
            )
        )
        count = len(active_count.all())
        
        # Update room participant count
        room_result = await db.execute(
            select(Room).where(Room.id == room_id)
        )
        room_obj = room_result.first()
        if room_obj:
            room_obj.participant_count = count

        await db.commit()

        return {"success": True}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove user from room: {str(e)}"
        )
