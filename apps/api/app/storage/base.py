from pathlib import Path
from typing import BinaryIO, Protocol


class Storage(Protocol):
    """Opslag van bestanden onder een sleutel (relatief pad met "/"). Later uit te breiden
    met een S3-compatibele adapter zonder de rest van de code te raken."""

    def write(self, key: str, data: bytes) -> None: ...

    def open(self, key: str) -> BinaryIO: ...

    def exists(self, key: str) -> bool: ...

    def local_path(self, key: str) -> Path:
        """Pad op schijf. Alleen voor adapters die lokaal staan (zip-export, FileResponse)."""
        ...
