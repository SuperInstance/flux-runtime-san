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
  - Dhātu (verbal roots)        → opcode generation
  - Vocabulary tiling (4 levels) → NL → bytecode mapping
"""

__version__ = "0.3.0"
__title__ = "FLUX-san"
__sanskrit_title__ = "प्रवाहिनी"

from flux_san.vibhakti import Vibhakti, ScopeLevel
from flux_san.lakara import Lakara, ExecutionMode
from flux_san.samasa import SamasaType, SamasaParser
from flux_san.interpreter import FluxInterpreterSan
from flux_san.vm import FluxVMSan, Opcode, ScopedRegister, VibhaktiScopeError
from flux_san.dhatu import Dhatu, DhatuCompiler, Gana, Pada, Conjugation
from flux_san.sandhi import SandhiEngine, SandhiRule, SandhiToken, SandhiType
from flux_san.vocabulary import VocabularyTable, VocabTile, VocabLevel
from flux_san.scope_manager import VibhaktiScopeManager, ScopeCode as SanScopeCode, ScopeFrame, ScopeTransition
from flux_san.dhatu_resolver import DhatuOpcodeResolver, DhatuProperty, Transitivity, Valency, SemanticClass, ThiArity
from flux_san.code_merger import SandhiCodeMerger, MergedCode, MergeType, MergeEffect, ConceptFusion

__all__ = [
    # Core systems
    "Vibhakti",
    "ScopeLevel",
    "Lakara",
    "ExecutionMode",
    "SamasaType",
    "SamasaParser",
    "FluxInterpreterSan",
    # VM
    "FluxVMSan",
    "Opcode",
    "ScopedRegister",
    "VibhaktiScopeError",
    # Dhātu
    "Dhatu",
    "DhatuCompiler",
    "Gana",
    "Pada",
    "Conjugation",
    # Sandhi
    "SandhiEngine",
    "SandhiRule",
    "SandhiToken",
    "SandhiType",
    # Vocabulary
    "VocabularyTable",
    "VocabTile",
    "VocabLevel",
    # R8: Scope Management, Extended Dhātu, Code Merging
    "VibhaktiScopeManager",
    "SanScopeCode",
    "ScopeFrame",
    "ScopeTransition",
    "DhatuOpcodeResolver",
    "DhatuProperty",
    "Transitivity",
    "Valency",
    "SemanticClass",
    "ThiArity",
    "SandhiCodeMerger",
    "MergedCode",
    "MergeType",
    "MergeEffect",
    "ConceptFusion",
]
