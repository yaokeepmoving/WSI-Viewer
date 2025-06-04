import logging
from pathlib import Path

from .lru_reader_cache import LRUReaderCache

logger = logging.getLogger(__name__)


class WSIService:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        self._reader_cache = LRUReaderCache()

    def open_slide(self, slide_path: str):
        slide_obj = self._reader_cache.add(slide_path)
        return slide_obj.open_slide(slide_path)

    def get_tile(self,
                 slide_path: str,
                 x: int,
                 y: int,
                 level: int,
                 size: int = 512):
        slide_obj = self._reader_cache.add(slide_path)
        return slide_obj.get_tile(slide_path, x, y, level, size)
