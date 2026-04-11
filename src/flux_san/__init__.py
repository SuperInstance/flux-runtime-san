"""
FLUX-san — प्रवाहिनी भाषा सार्वभौमिक निष्पादनम्
Fluent Language Universal Execution — Sanskrit-first Natural Language Runtime

Sanskrit grammar (Pāṇini's Aṣṭādhyāyī) IS a formal system — this makes
Sanskrit the most natural language for programming.

Architecture:
  - Aṣṭau-vibhakti (8 cases)   → 8 scope levels
  - Aṣṭau-lakāra (8 tenses)    → 8 execution modes
  - Samāsa (compounds)          → type composition
  - Tri-vacana (3 numbers)      → arity types (1, 2, N)
  - Tri-liṅga (3 genders)      → 3 type families
  - Sandhi resolution           → token fusion / splitting
"""

__version__ = "0.1.0"
__title__ = "FLUX-san"
__sanskrit_title__ = "प्रवाहिनी"

from flux_san.vibhakti import Vibhakti, ScopeLevel
from flux_san.lakara import Lakara, ExecutionMode
from flux_san.samasa import SamasaType, SamasaParser
from flux_san.interpreter import FluxInterpreterSan

__all__ = [
    "Vibhakti",
    "ScopeLevel",
    "Lakara",
    "ExecutionMode",
    "SamasaType",
    "SamasaParser",
    "FluxInterpreterSan",
]
