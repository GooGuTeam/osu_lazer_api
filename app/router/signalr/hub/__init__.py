from __future__ import annotations

from .hub import Hub
from .metadata import MetadataHub
from .multiplayer import MultiplayerHub
from .notifications import NotificationsHub
from .spectator import SpectatorHub

SpectatorHubs = SpectatorHub()
MultiplayerHubs = MultiplayerHub()
MetadataHubs = MetadataHub()
NotificationsHubs = NotificationsHub()
Hubs: dict[str, Hub] = {
    "spectator": SpectatorHubs,
    "multiplayer": MultiplayerHubs,
    "metadata": MetadataHubs,
    "notifications": NotificationsHubs,
}
