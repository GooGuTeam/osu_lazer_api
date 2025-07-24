from __future__ import annotations

from enum import IntEnum
from typing import Any

import msgpack
from pydantic import BaseModel, model_validator

SEP = b"\x1e"


class PacketType(IntEnum):
    INVOCATION = 1
    STREAM_ITEM = 2
    COMPLETION = 3
    STREAM_INVOCATION = 4
    CANCEL_INVOCATION = 5
    PING = 6
    CLOSE = 7

class ResultKind(IntEnum):
    ERROR = 1
    VOID = 2
    HAS_VALUE = 3


def parse_packet(data: bytes) -> tuple[PacketType, list[Any]]:
    length, offset = decode_varint(data)
    message_data = data[offset : offset + length]
    unpacked = msgpack.unpackb(message_data, raw=False)
    return PacketType(unpacked[0]), unpacked[1:]


def encode_varint(value: int) -> bytes:
    result = []
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    result = 0
    shift = 0
    pos = offset

    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if (byte & 0x80) == 0:
            break
        shift += 7

    return result, pos
