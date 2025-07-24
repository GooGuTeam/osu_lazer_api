from __future__ import annotations

from app.models.spectator_hub import FrameDataBundle, SpectatorState

from .hub import Client, Hub


class SpectatorHub(Hub):
    async def BeginPlaySession(
        self, client: Client, score_token: int, state: SpectatorState
    ) -> None:
        ...

    async def SendFrameData(
        self, client: Client, frame_data: FrameDataBundle
    ) -> None:
        ...
