"""
Common module — общие утилиты и компоненты.

Модуль предоставляет переиспользуемые компоненты,
которые могут использоваться в разных слоях приложения.
"""

from .mappers import to_domain, from_domain, to_data_model, from_data_model
from .application_state import AppStateStore

__all__ = [
    "to_domain",
    "from_domain",
    "to_data_model",
    "from_data_model",
    "AppStateStore",
]
