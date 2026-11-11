from __future__ import annotations

from .admin_tools import register_admin_tools
from .character_features import register_character_features
from .store_features import register_store_and_util_features
from .world_features import register_world_features
from .social_features import register_social_features


def register_feature_modules(application):
    register_admin_tools(application)
    register_character_features(application)
    register_store_and_util_features(application)
    register_world_features(application)
    register_social_features(application)
