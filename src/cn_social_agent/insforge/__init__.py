from typing import Optional

from .client import InsForgeClient, InsForgeError
from .config import InsForgeConfig, load_config
from .auth import InsForgeAuth, InsForgeUser
from .db import InsForgeDB
from .storage import InsForgeStorage
from .llm import InsForgeLLM
from .schedules import InsForgeSchedules
from .secrets import InsForgeSecrets
from .email import InsForgeEmail
from .webhooks import InsForgeWebhooks
from .analytics import InsForgeAnalytics


class InsForge:
    """Convenience wrapper holding all InsForge sub-clients."""

    def __init__(self, config: Optional[InsForgeConfig] = None):
        self.config = config or load_config()
        self._client = InsForgeClient(self.config)
        self.auth = InsForgeAuth(self._client)
        self.db = InsForgeDB(self._client)
        self.storage = InsForgeStorage(self._client)
        self.llm = InsForgeLLM(self._client)
        self.schedules = InsForgeSchedules(self._client)
        self.secrets = InsForgeSecrets(self._client)
        self.email = InsForgeEmail(self._client)
        self.webhooks = InsForgeWebhooks(self._client)
        self.analytics = InsForgeAnalytics(self._client)

    async def initialize(self):
        if self.config.enabled:
            await self._client.admin_login()

    async def close(self):
        await self._client.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, *args):
        await self.close()

    @property
    def enabled(self) -> bool:
        return self.config.enabled


__all__ = [
    "InsForge",
    "InsForgeClient",
    "InsForgeConfig",
    "InsForgeAuth",
    "InsForgeUser",
    "InsForgeDB",
    "InsForgeStorage",
    "InsForgeLLM",
    "InsForgeSchedules",
    "InsForgeSecrets",
    "InsForgeEmail",
    "InsForgeWebhooks",
    "InsForgeAnalytics",
    "InsForgeError",
    "load_config",
]
