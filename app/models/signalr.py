from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class MessagePackArrayModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def unpack(cls, v: Any) -> Any:
        if isinstance(v, list):
            fields = list(cls.model_fields.keys())
            if len(v) != len(fields):
                raise ValueError(f"Expected list of length {len(fields)}, got {len(v)}")
            return dict(zip(fields, v))
        return v


class Transport(BaseModel):
    transport: str
    transfer_formats: list[str] = Field(
        default_factory=lambda: ["Binary"], alias="transferFormats"
    )


class NegotiateResponse(BaseModel):
    connectionId: str
    connectionToken: str
    negotiateVersion: int = 1
    availableTransports: list[Transport]
