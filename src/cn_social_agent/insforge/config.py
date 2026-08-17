"""InsForge SDK configuration - reads settings from environment / config."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Try to load .env from project root or insforge/ directory
try:
    from dotenv import load_dotenv

    _search_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "insforge" / ".env",
        Path(__file__).resolve().parent.parent.parent.parent.parent / "insforge" / ".env",
    ]
    for _p in _search_paths:
        if _p.exists():
            load_dotenv(_p)
            break
except ImportError:
    pass


@dataclass
class InsForgeStorageConfig:
    """InsForge S3-compatible storage configuration."""
    s3_endpoint: str = ""
    s3_region: str = "us-east-2"
    access_key_id: str = ""
    secret_access_key: str = ""
    max_file_size: int = 50 * 1024 * 1024  # 50MB


@dataclass
class InsForgeLLMConfig:
    """InsForge Model Gateway configuration."""
    enabled: bool = False
    api_key: str = ""
    default_model: str = "openai/gpt-4o-mini"


@dataclass
class InsForgeConfig:
    """Root InsForge SDK configuration."""
    enabled: bool = True
    api_url: str = "http://localhost:7130"
    auth_url: str = "http://localhost:7130"
    anon_key: str = ""
    admin_username: str = "admin"
    admin_password: str = "change-this-password"
    jwt_secret: str = ""
    postgrest_url: str = "http://localhost:5434"
    storage: InsForgeStorageConfig = field(default_factory=InsForgeStorageConfig)
    llm: InsForgeLLMConfig = field(default_factory=InsForgeLLMConfig)


def load_config() -> InsForgeConfig:
    """Load InsForge configuration from environment variables."""
    cfg = InsForgeConfig(
        enabled=os.getenv("INSFORGE_ENABLED", "true").lower() == "true",
        api_url=os.getenv("INSFORGE_API_URL", "http://localhost:7130"),
        auth_url=os.getenv("INSFORGE_AUTH_URL", "http://localhost:7130"),
        anon_key=os.getenv("INSFORGE_ANON_KEY", ""),
        admin_username=os.getenv("INSFORGE_ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("INSFORGE_ADMIN_PASSWORD", "change-this-password"),
        jwt_secret=os.getenv("INSFORGE_JWT_SECRET", ""),
        postgrest_url=os.getenv(
            "INSFORGE_PGRST_URL",
            f"http://localhost:{os.getenv('INSFORGE_PGRST_PORT', '5434')}",
        ),
        storage=InsForgeStorageConfig(
            s3_endpoint=os.getenv("INSFORGE_S3_ENDPOINT", ""),
            s3_region=os.getenv("INSFORGE_S3_REGION", "us-east-2"),
            access_key_id=os.getenv("INSFORGE_S3_ACCESS_KEY_ID", ""),
            secret_access_key=os.getenv("INSFORGE_S3_SECRET_ACCESS_KEY", ""),
            max_file_size=int(os.getenv("INSFORGE_MAX_FILE_SIZE", str(50 * 1024 * 1024))),
        ),
        llm=InsForgeLLMConfig(
            enabled=bool(os.getenv("INSFORGE_OPENROUTER_API_KEY")),
            api_key=os.getenv("INSFORGE_OPENROUTER_API_KEY", ""),
            default_model=os.getenv("INSFORGE_LLM_MODEL", "openai/gpt-4o-mini"),
        ),
    )
    return cfg
