from datetime import datetime
from typing import TYPE_CHECKING

from app.models.model import UTCBaseModel

from sqlalchemy import Column, DateTime
from sqlmodel import BigInteger, Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from .lazer_user import User


class Team(SQLModel, UTCBaseModel, table=True):
    __tablename__ = "teams"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    name: str = Field(max_length=100)
    short_name: str = Field(max_length=10)
    flag_url: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    members: list["TeamMember"] = Relationship(back_populates="team")


class TeamMember(SQLModel, UTCBaseModel, table=True):
    __tablename__ = "team_members"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(sa_column=Column(BigInteger, ForeignKey("lazer_users.id")))
    team_id: int = Field(foreign_key="teams.id")
    joined_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(
        back_populates="team_membership", sa_relationship_kwargs={"lazy": "joined"}
    )
    team: "Team" = Relationship(
        back_populates="members", sa_relationship_kwargs={"lazy": "joined"}
    )
