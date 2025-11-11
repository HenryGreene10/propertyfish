import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    TABLE_SEARCH: str = os.getenv("TABLE_SEARCH", "property_search")


settings = Settings()
