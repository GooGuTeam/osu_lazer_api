"""LIO (Legacy IO) router for osu-server-spectator compatibility."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import col, select

from app.database.lazer_user import User
from app.database.playlists import Playlist as DBPlaylist
from app.database.room import Room
from app.database.room_participated_user import RoomParticipatedUser
from app.dependencies.database import Database
from app.models.multiplayer_hub import PlaylistItem as HubPlaylistItem
from app.models.room import MatchType, QueueMode, RoomStatus
from app.utils import utcnow

router = APIRouter(prefix="/_lio", tags=["LIO"])


class RoomCreateRequest(BaseModel):
    """Request model for creating a multiplayer room."""
    name: str
    user_id: int
    password: str | None = None
    match_type: str = "HeadToHead"
    queue_mode: str = "HostOnly"
    initial_playlist: List[Dict[str, Any]] = []
    playlist: List[Dict[str, Any]] = []


def verify_request_signature(request: Request, timestamp: str, body: bytes) -> bool:
    """
    Verify HMAC signature for shared interop requests.
    
    Args:
        request: FastAPI request object
        timestamp: Request timestamp
        body: Request body bytes
        
    Returns:
        bool: True if signature is valid
        
    Note:
        Currently skips verification in development.
        In production, implement proper HMAC verification.
    """
    # TODO: Implement proper HMAC verification for production
    return True


async def _validate_user_exists(db: Database, user_id: int) -> User:
    """Validate that a user exists in the database."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    return user


def _parse_room_enums(match_type: str, queue_mode: str) -> tuple[MatchType, QueueMode]:
    """Parse and validate room type enums."""
    try:
        match_type_enum = MatchType(match_type.lower())
    except ValueError:
        match_type_enum = MatchType.HEAD_TO_HEAD

    try:
        queue_mode_enum = QueueMode(queue_mode.lower())
    except ValueError:
        queue_mode_enum = QueueMode.HOST_ONLY
    
    return match_type_enum, queue_mode_enum


def _coerce_playlist_item(item_data: Dict[str, Any], default_order: int, host_user_id: int) -> Dict[str, Any]:
    """
    Normalize playlist item data with default values.
    
    Args:
        item_data: Raw playlist item data
        default_order: Default playlist order
        host_user_id: Host user ID for default owner
        
    Returns:
        Dict with normalized playlist item data
    """
    # Use host_user_id if owner_id is 0 or not provided
    owner_id = item_data.get("owner_id", host_user_id)
    if owner_id == 0:
        owner_id = host_user_id
    
    return {
        "owner_id": owner_id,
        "ruleset_id": item_data.get("ruleset_id", 0),
        "beatmap_id": item_data.get("beatmap_id"),
        "required_mods": item_data.get("required_mods", []),
        "allowed_mods": item_data.get("allowed_mods", []),
        "expired": bool(item_data.get("expired", False)),
        "playlist_order": item_data.get("playlist_order", default_order),
        "played_at": item_data.get("played_at", None),
        "freestyle": bool(item_data.get("freestyle", True)),
        "beatmap_checksum": item_data.get("beatmap_checksum", ""),
        "star_rating": item_data.get("star_rating", 0.0),
    }


def _validate_playlist_items(items: List[Dict[str, Any]]) -> None:
    """Validate playlist items data."""
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one playlist item is required to create a room"
        )
    
    for idx, item in enumerate(items):
        if item["beatmap_id"] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Playlist item at index {idx} missing beatmap_id"
            )
        
        ruleset_id = item["ruleset_id"]
        if not isinstance(ruleset_id, int) or not (0 <= ruleset_id <= 3):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Playlist item at index {idx} has invalid ruleset_id {ruleset_id}"
            )


async def _create_room(db: Database, room_data: Dict[str, Any]) -> tuple[Room, int]:
    """Create a new multiplayer room."""
    host_user_id = room_data.get("user_id")
    room_name = room_data.get("name", "Unnamed Room")
    password = room_data.get("password")
    match_type = room_data.get("match_type", "HeadToHead")
    queue_mode = room_data.get("queue_mode", "HostOnly")

    if not host_user_id or not isinstance(host_user_id, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid user_id"
        )

    # Validate host user exists
    await _validate_user_exists(db, host_user_id)
    
    # Parse room type enums
    match_type_enum, queue_mode_enum = _parse_room_enums(match_type, queue_mode)

    # Create room
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
    
    return room, host_user_id


async def _add_playlist_items(db: Database, room_id: int, room_data: Dict[str, Any], host_user_id: int) -> None:
    """Add playlist items to the room."""
    initial_playlist = room_data.get("initial_playlist", [])
    legacy_playlist = room_data.get("playlist", [])
    
    items_raw: List[Dict[str, Any]] = []
    
    # Process initial playlist
    for i, item in enumerate(initial_playlist):
        if hasattr(item, "dict"):
            item = item.dict()
        items_raw.append(_coerce_playlist_item(item, i, host_user_id))
    
    # Process legacy playlist
    start_index = len(items_raw)
    for j, item in enumerate(legacy_playlist, start=start_index):
        items_raw.append(_coerce_playlist_item(item, j, host_user_id))
    
    # Validate playlist items
    _validate_playlist_items(items_raw)
    
    # Insert playlist items
    for item_data in items_raw:
        hub_item = HubPlaylistItem(
            id=-1,  # Placeholder, will be assigned by add_to_db
            owner_id=item_data["owner_id"],
            ruleset_id=item_data["ruleset_id"],
            expired=item_data["expired"],
            playlist_order=item_data["playlist_order"],
            played_at=item_data["played_at"],
            allowed_mods=item_data["allowed_mods"],
            required_mods=item_data["required_mods"],
            beatmap_id=item_data["beatmap_id"],
            freestyle=item_data["freestyle"],
            beatmap_checksum=item_data["beatmap_checksum"],
            star_rating=item_data["star_rating"],
        )
        await DBPlaylist.add_to_db(hub_item, room_id=room_id, session=db)


async def _add_host_as_participant(db: Database, room_id: int, host_user_id: int) -> None:
    """Add the host as a room participant and update participant count."""
    participant = RoomParticipatedUser(room_id=room_id, user_id=host_user_id)
    db.add(participant)
    
    await _update_room_participant_count(db, room_id)


async def _update_room_participant_count(db: Database, room_id: int) -> None:
    """Update the participant count for a room."""
    # Count active participants
    active_participants = await db.execute(
        select(RoomParticipatedUser).where(
            RoomParticipatedUser.room_id == room_id,
            col(RoomParticipatedUser.left_at).is_(None)
        )
    )
    count = len(active_participants.all())
    
    # Update room participant count
    room_result = await db.execute(select(Room).where(Room.id == room_id))
    room_obj = room_result.scalar_one_or_none()
    if room_obj:
        room_obj.participant_count = count


async def _verify_room_password(db: Database, room_id: int, provided_password: str | None) -> None:
    """Verify room password if required."""
    room_result = await db.execute(
        select(Room.password).where(Room.id == room_id)
    )
    room_password = room_result.scalar_one_or_none()
    
    if room_password is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )
    
    if room_password and provided_password != room_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid password"
        )


async def _add_or_update_participant(db: Database, room_id: int, user_id: int) -> None:
    """Add a user as participant or update existing participation."""
    existing_result = await db.execute(
        select(RoomParticipatedUser).where(
            RoomParticipatedUser.room_id == room_id,
            RoomParticipatedUser.user_id == user_id
        )
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        # Rejoin room
        existing.left_at = None
        existing.joined_at = utcnow()
    else:
        # New participant
        participant = RoomParticipatedUser(room_id=room_id, user_id=user_id)
        db.add(participant)


# ===== API ENDPOINTS =====

@router.post("/multiplayer/rooms")
async def create_multiplayer_room(
    request: Request,
    room_data: Dict[str, Any],
    db: Database,
    timestamp: str = "",
) -> int:
    """Create a new multiplayer room with initial playlist."""
    try:
        # Verify request signature
        body = await request.body()
        if not verify_request_signature(request, timestamp, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature"
            )

        # Parse room data if string
        if isinstance(room_data, str):
            room_data = json.loads(room_data)

        print(f"Creating room with data: {room_data}")

        # Create room
        room, host_user_id = await _create_room(db, room_data)
        room_id = room.id

        try:
            # Add playlist items
            await _add_playlist_items(db, room_id, room_data, host_user_id)
            
            # Add host as participant
            await _add_host_as_participant(db, room_id, host_user_id)
            
            await db.commit()
            return room_id
            
        except HTTPException:
            # Clean up room if playlist creation fails
            await db.delete(room)
            await db.commit()
            raise

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {str(e)}"
        )
    except HTTPException:
        raise
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
    user_data: Dict[str, Any] | None = None,
    timestamp: str = "",
) -> Dict[str, Any]:
    """Add a user to a multiplayer room."""
    try:
        # Verify request signature
        body = await request.body()
        if not verify_request_signature(request, timestamp, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature"
            )

        # Verify room password if provided
        provided_password = user_data.get("password") if user_data else None
        await _verify_room_password(db, room_id, provided_password)

        # Add or update participant
        await _add_or_update_participant(db, room_id, user_id)
        
        # Update participant count
        await _update_room_participant_count(db, room_id)
        
        await db.commit()
        return {"success": True}

    except HTTPException:
        raise
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
) -> Dict[str, Any]:
    """Remove a user from a multiplayer room."""
    try:
        # Verify request signature
        body = await request.body()
        if not verify_request_signature(request, timestamp, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature"
            )

        # Mark user as left
        result = await db.execute(
            select(RoomParticipatedUser).where(
                RoomParticipatedUser.room_id == room_id,
                RoomParticipatedUser.user_id == user_id,
                col(RoomParticipatedUser.left_at).is_(None)
            )
        )
        participation = result.scalar_one_or_none()
        
        if participation:
            participation.left_at = utcnow()

        # Update participant count
        await _update_room_participant_count(db, room_id)
        
        await db.commit()
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove user from room: {str(e)}"
        )