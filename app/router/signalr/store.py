from __future__ import annotations

import asyncio
import sys
from typing import Any, Literal

from app.router.signalr.packet import ResultKind


class ResultStore:
    def __init__(self) -> None:
        self._seq: int = 1
        self._futures: dict[str, asyncio.Future] = {}

    @property
    def current_invocation_id(self) -> int:
        return self._seq

    def get_invocation_id(self) -> str:
        s = self._seq
        self._seq = (self._seq + 1) % sys.maxsize
        return str(s)

    def add_result(
        self, invocation_id: str, type: ResultKind, result: dict[str, Any] | None
    ) -> None:
        if isinstance(invocation_id, str) and invocation_id.isdecimal():
            if future := self._futures.get(invocation_id):
                future.set_result((type, result))

    async def fetch(
        self,
        invocation_id: str,
        timeout: float | None,  # noqa: ASYNC109
    ) -> (
        tuple[Literal[ResultKind.ERROR], str]
        | tuple[Literal[ResultKind.VOID], None]
        | tuple[Literal[ResultKind.HAS_VALUE], Any]
    ):
        future = asyncio.get_event_loop().create_future()
        self._futures[invocation_id] = future
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            del self._futures[invocation_id]
