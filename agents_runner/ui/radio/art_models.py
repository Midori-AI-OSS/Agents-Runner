from __future__ import annotations

from pydantic import BaseModel


class ArtPayload(BaseModel):
    art_url: str
    has_art: bool
    track_id: str
    mime: str
    channel: str
