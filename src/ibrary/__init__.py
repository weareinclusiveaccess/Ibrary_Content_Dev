"""
IBrary - Automated Content Rewording Component for Accessible Secondary School Learning

A standardized content rewording component that transforms curriculum-aligned
secondary school content into simplified, relatable, accessibility-aware explanations
optimized for visually impaired learners and audio-first delivery.
"""

__version__ = "0.1.0"

from ibrary.core.transformer import ContentTransformer
from ibrary.profiles.profile_manager import ProfileManager

__all__ = [
    "ContentTransformer",
    "ProfileManager",
]
