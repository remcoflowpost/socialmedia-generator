from functools import lru_cache

from app.settings import get_settings
from app.storage.base import Storage
from app.storage.local import LocalStorage


@lru_cache
def get_storage() -> Storage:
    return LocalStorage(get_settings().storage_root)


__all__ = ["LocalStorage", "Storage", "get_storage"]
