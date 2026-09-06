from .base import ConnectorConfig, ConnectorStatus, IdeaConnector, RawMaterial
from .competitor import CompetitorConnector
from .github_trending import GitHubTrendingConnector
from .hackernews import HackerNewsConnector
from .knowledge_base import KnowledgeBaseConnector
from .manager import ConnectorManager, manager
from .pain_point import PainPointConnector
from .sspai import SspaiConnector
from .v2ex import V2EXConnector
from .zhihu import ZhihuConnector

__all__ = [
    "ConnectorConfig",
    "ConnectorStatus",
    "ConnectorManager",
    "IdeaConnector",
    "RawMaterial",
    "GitHubTrendingConnector",
    "HackerNewsConnector",
    "V2EXConnector",
    "SspaiConnector",
    "ZhihuConnector",
    "CompetitorConnector",
    "PainPointConnector",
    "KnowledgeBaseConnector",
    "manager",
]

manager.register(GitHubTrendingConnector)
manager.register(HackerNewsConnector)
manager.register(V2EXConnector)
manager.register(SspaiConnector)
manager.register(ZhihuConnector)
manager.register(CompetitorConnector)
manager.register(PainPointConnector)
manager.register(KnowledgeBaseConnector)
