from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ollama
    ollama_base_url: str = Field(default="http://ollama:11434")
    ollama_model: str = Field(default="llama3.2")

    # SearXNG
    searxng_url: str = Field(default="http://searxng:8080")

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")

    # Upload limits
    upload_max_size_mb: int = Field(default=50)

    # Tor proxy hosts — comma-separated "host:port" (set via docker-compose env)
    tor_hosts: str = Field(default="tor-1:9050,tor-2:9050,tor-3:9050")

    # Tor proxy ports — comma-separated string (legacy, used by tor_port_list)
    tor_ports: str = Field(default="9050,9051,9052")

    # Anti-ban delays (seconds)
    search_delay_min: float = Field(default=1.5)
    search_delay_max: float = Field(default=4.0)

    # Proxy refresh interval (seconds)
    proxy_refresh_interval: int = Field(default=1800)

    # Max search queries per document
    max_queries_per_doc: int = Field(default=15)

    @field_validator("search_delay_min", "search_delay_max", mode="after")
    @classmethod
    def _validate_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Delay must be non-negative")
        return v

    @property
    def tor_port_list(self) -> list[int]:
        """Parse TOR_PORTS string into list of integers."""
        return [int(p.strip()) for p in self.tor_ports.split(",") if p.strip()]

    @property
    def upload_max_size_bytes(self) -> int:
        return self.upload_max_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
