from __future__ import annotations

from .hub import Hub
from .metadata import MetadataHub
from .multiplayer import MultiplayerHub
from .spectator import SpectatorHub

SpectatorHubs = SpectatorHub()
MultiplayerHubs = MultiplayerHub()
MetadataHubs = MetadataHub()
Hubs: dict[str, Hub] = {
    "spectator": SpectatorHubs,
    "multiplayer": MultiplayerHubs,
    "metadata": MetadataHubs,
}
