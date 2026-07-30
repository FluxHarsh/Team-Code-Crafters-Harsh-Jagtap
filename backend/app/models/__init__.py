"""
Import every model here so `Base.metadata` is fully populated no matter
which module first imports `app.models` — this is what Alembic's
env.py points autogenerate at.
"""

from app.db.base import Base
from app.models.agent_run_log import AgentRunLog
from app.models.chat_message import CHAT_PHASES, ChatMessage
from app.models.critique_history import CritiqueHistory
from app.models.document import Document
from app.models.github_connection import GithubConnection
from app.models.postmortem_embedding import EMBEDDING_DIM, PostmortemEmbedding
from app.models.project import PROJECT_STATUSES, Project

__all__ = [
    "Base",
    "Project",
    "PROJECT_STATUSES",
    "Document",
    "CritiqueHistory",
    "GithubConnection",
    "AgentRunLog",
    "ChatMessage",
    "CHAT_PHASES",
    "PostmortemEmbedding",
    "EMBEDDING_DIM",
]
