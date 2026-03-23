"""
IBrary - Automated Content Rewording Component for Accessible Secondary School Learning

A standardized content rewording component that transforms curriculum-aligned
secondary school content into simplified, relatable, accessibility-aware explanations
optimized for visually impaired learners and audio-first delivery.
"""

__version__ = "0.1.0"

# Optional imports for legacy/optional modules so pipeline and Alembic can run
try:
    from ibrary.core.transformer import ContentTransformer
except ModuleNotFoundError:
    ContentTransformer = None  # type: ignore[misc, assignment]
try:
    from ibrary.profiles.profile_manager import ProfileManager
except ModuleNotFoundError:
    ProfileManager = None  # type: ignore[misc, assignment]

__all__ = [
    "ContentTransformer",
    "ProfileManager",
]
