from pathlib import Path, PurePosixPath
from typing import BinaryIO


class LocalStorage:
    """Opslag op een lokale map of een gemounte NAS-share.

    In docker wordt de NAS als volume gemount (zie docker-compose.yml); binnen de container
    is het dan een gewoon POSIX-pad. Sleutels gebruiken altijd "/" als scheidingsteken.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def local_path(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"ongeldige opslagsleutel: {key}")
        return self.root.joinpath(*relative.parts)

    def write(self, key: str, data: bytes) -> None:
        path = self.local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def open(self, key: str) -> BinaryIO:
        return self.local_path(key).open("rb")

    def exists(self, key: str) -> bool:
        return self.local_path(key).is_file()
