"""
Aṣṭau-lakāra — The Eight Execution Modes
===========================================

Sanskrit's lakāras (tense/mood markers) map to 8 execution strategies in FLUX.
Each lakāra determines HOW a verb's action is executed — not just WHEN.

  Lakāra                Sanskrit       Execution Mode
  ───────────────────────────────────────────────────────────────
  1. लट् (laṭ)          → laṭ          normal execution
  2. लङ् (laṅ)          → laṅ          branch / conditional execution
  3. लिट् (liṭ)          → liṭ          verified / cached execution
  4. लुङ् (luṅ)          → luṅ          immediate / atomic execution
  5. लृट् (lṛṭ)          → lṛṭ          future / deferred execution
  6. लृङ् (lṛṅ)          → lṛṅ          conditional (liṅ) → speculative execution
  7. विधिलिङ् (vidhiliṅ) → vidhiliṅ    potential / speculative execution
  8. आशीर्लिङ् (āśīrliṅ) → āśīrliṅ    imperative / forced execution

From Pāṇini's Aṣṭādhyāyī:
  lakāraḥ tiṅ-antānāṃ dhātu-śabda-vibhāgaḥ
  "lakāra is the tense/mood classification of verbal endings (tiṅ)"
"""

from __future__ import annotations

from enum import IntEnum
from dataclasses import dataclass
from typing import Callable, Any


class Lakara(IntEnum):
    """Aṣṭau-lakāra — the 8 tense/mood markers of Sanskrit as execution modes."""
    LAT       = 1  # लट्       — Present (laṭ)           → normal execution
    LAN       = 2  # लङ्       — Imperfect (laṅ)        → conditional / branch
    LIT       = 3  # लिट्       — Perfect (liṭ)          → verified / cached
    LUN       = 4  # लुङ्       — Aorist (luṅ)          → immediate / atomic
    LRIT      = 5  # लृट्       — Future (lṛṭ)          → deferred / future
    LRUNG     = 6  # लृङ्       — Conditional (lṛṅ)     → speculative execution
    VIDHILING = 7  # विधिलिङ्  — Potential (vidhiliṅ)   → speculative execution
    ASIRLING  = 8  # आशीर्लिङ् — Imperative (āśīrliṅ)  → forced execution

    @property
    def devanagari(self) -> str:
        return _DEVANAGARI_NAMES[self]

    @property
    def iast(self) -> str:
        return _IAST_NAMES[self]

    @property
    def english(self) -> str:
        return _ENGLISH_NAMES[self]

    @property
    def execution_mode(self) -> ExecutionMode:
        return _LAKARA_TO_EXEC[self]


class ExecutionMode(IntEnum):
    """FLUX execution strategies mapped from lakāras."""
    NORMAL       = 0  # Standard sequential execution
    CONDITIONAL  = 1  # Branch on condition
    VERIFIED     = 2  # Execute with verification / caching
    ATOMIC       = 3  # Immediate, uninterruptible execution
    DEFERRED     = 4  # Future / lazy execution
    SPECULATIVE  = 5  # Speculative / try-and-rollback
    FORCED       = 6  # Override all guards, forced execution


_DEVANAGARI_NAMES: dict[Lakara, str] = {
    Lakara.LAT:       "लट्",
    Lakara.LAN:       "लङ्",
    Lakara.LIT:       "लिट्",
    Lakara.LUN:       "लुङ्",
    Lakara.LRIT:      "लृट्",
    Lakara.LRUNG:     "लृङ्",
    Lakara.VIDHILING: "विधिलिङ्",
    Lakara.ASIRLING:  "आशीर्लिङ्",
}

_IAST_NAMES: dict[Lakara, str] = {
    Lakara.LAT:       "laṭ",
    Lakara.LAN:       "laṅ",
    Lakara.LIT:       "liṭ",
    Lakara.LUN:       "luṅ",
    Lakara.LRIT:      "lṛṭ",
    Lakara.LRUNG:     "lṛṅ",
    Lakara.VIDHILING: "vidhiliṅ",
    Lakara.ASIRLING:  "āśīrliṅ",
}

_ENGLISH_NAMES: dict[Lakara, str] = {
    Lakara.LAT:       "present",
    Lakara.LAN:       "imperfect",
    Lakara.LIT:       "perfect",
    Lakara.LUN:       "aorist",
    Lakara.LRIT:      "future",
    Lakara.LRUNG:     "conditional",
    Lakara.VIDHILING: "potential",
    Lakara.ASIRLING:  "imperative",
}

_LAKARA_TO_EXEC: dict[Lakara, ExecutionMode] = {
    Lakara.LAT:       ExecutionMode.NORMAL,
    Lakara.LAN:       ExecutionMode.CONDITIONAL,
    Lakara.LIT:       ExecutionMode.VERIFIED,
    Lakara.LUN:       ExecutionMode.ATOMIC,
    Lakara.LRIT:      ExecutionMode.DEFERRED,
    Lakara.LRUNG:     ExecutionMode.CONDITIONAL,  # lṛṅ = conditional mood
    Lakara.VIDHILING: ExecutionMode.SPECULATIVE,
    Lakara.ASIRLING:  ExecutionMode.FORCED,
}


@dataclass
class LakaraContext:
    """
    Execution context qualified by a lakāra.
    Determines how the interpreter dispatches an action.
    """
    lakara: Lakara
    condition: bool | None = None  # Used for CONDITIONAL mode
    cache_key: str | None = None   # Used for VERIFIED mode
    rollback_fn: Callable[[], None] | None = None  # Used for SPECULATIVE mode

    @property
    def mode(self) -> ExecutionMode:
        return self.lakara.execution_mode

    @property
    def should_execute(self) -> bool:
        """Determine whether the action should execute under this lakāra."""
        match self.mode:
            case ExecutionMode.NORMAL:
                return True
            case ExecutionMode.CONDITIONAL:
                return self.condition is not None and self.condition
            case ExecutionMode.ATOMIC:
                return True  # Always executes, but atomically
            case ExecutionMode.FORCED:
                return True  # Always executes, overriding guards
            case ExecutionMode.VERIFIED:
                return self.cache_key is not None
            case ExecutionMode.DEFERRED:
                return False  # Deferred — queued for later
            case ExecutionMode.SPECULATIVE:
                return True  # Execute speculatively, may rollback
            case _:
                return True

    @property
    def bytecode_prefix(self) -> str:
        """Return the instruction prefix for this execution mode."""
        prefixes = {
            ExecutionMode.NORMAL:      "",
            ExecutionMode.CONDITIONAL: "COND ",
            ExecutionMode.VERIFIED:    "VERIFY ",
            ExecutionMode.ATOMIC:      "ATOMIC ",
            ExecutionMode.DEFERRED:    "DEFER ",
            ExecutionMode.SPECULATIVE: "SPEC ",
            ExecutionMode.FORCED:      "FORCE ",
        }
        return prefixes.get(self.mode, "")

    def __repr__(self) -> str:
        return (
            f"LakaraContext({self.lakara.devanagari}/{self.lakara.iast}, "
            f"mode={self.mode.name})"
        )


class LakaraDetector:
    """
    Detects lakāra from verbal endings or explicit markers.
    Pāṇini's tiṅ-pratyaya (verbal suffix) analysis.
    """

    # Common present-tense (laṭ) endings in IAST
    _lat_endings = ["ti", "tasi", "ti", "tavahi", "anti"]
    # Common imperfect (laṅ) endings
    _lan_endings = ["at", "ataḥ", "an", "itavahi", "antuḥ"]
    # Common imperative (āśīrliṅ / loṭ) endings
    _asirling_endings = ["bhava", "bhavataḥ", "bhavantu", "hi"]
    # Common potential (vidhiliṅ) endings
    _vidhiling_endings = ["et", "etām", "eran", "īṣṭa"]
    # Common aorist (luṅ) endings
    _lun_endings = ["aḥ", "iṣṭa", "am", "ata"]

    # Explicit lakāra markers in NL patterns
    _marker_to_lakara: dict[str, Lakara] = {
        "करोति":   Lakara.LAT,       # "does" (present)
        "akarot":  Lakara.LAN,       # "did" (imperfect)
        "cakāra":  Lakara.LIT,       # "has done" (perfect)
        "akarṣīt": Lakara.LUN,      # "did suddenly" (aorist)
        "kariṣyati": Lakara.LRIT,   # "will do" (future)
        "kuryāt":  Lakara.VIDHILING, # "might do" (potential)
        "karotu":  Lakara.ASIRLING,  # "let [him] do" (imperative)
        "kuryām":  Lakara.LRUNG,     # "would do" (conditional)
    }

    @classmethod
    def detect_from_ending(cls, word: str) -> Lakara | None:
        """Detect lakāra from a verb's IAST ending."""
        for ending in cls._asirling_endings:
            if word.endswith(ending):
                return Lakara.ASIRLING
        for ending in cls._vidhiling_endings:
            if word.endswith(ending):
                return Lakara.VIDHILING
        for ending in cls._lun_endings:
            if word.endswith(ending):
                return Lakara.LUN
        for ending in cls._lan_endings:
            if word.endswith(ending):
                return Lakara.LAN
        for ending in cls._lat_endings:
            if word.endswith(ending):
                return Lakara.LAT
        return None

    @classmethod
    def detect_from_marker(cls, marker: str) -> Lakara | None:
        """Detect lakāra from an explicit verbal marker."""
        return cls._marker_to_lakara.get(marker)

    @classmethod
    def make_context(cls, lakara: Lakara, **kwargs) -> LakaraContext:
        """Create a LakaraContext from a Lakara enum value."""
        return LakaraContext(lakara=lakara, **kwargs)

    @classmethod
    def all_lakaras_table(cls) -> str:
        """Pretty-print the complete lakāra→execution mode mapping table."""
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║  Aṣṭau-lakāra — Eight Execution Modes                     ║",
            "║  पाणिनेः कालप्रकरणम् → FLUX Execution Strategies           ║",
            "╠═════════╦═════════════╦═══════════════╦═════════════════════╣",
            "║  Mode   ║ Sanskrit   ║ English      ║ FLUX Execution      ║",
            "╠═════════╬═════════════╬═══════════════╬═════════════════════╣",
        ]
        for lk in Lakara:
            lines.append(
                f"║  {lk.value:>2}     ║ {lk.devanagari:<11s} ║ {lk.english:<13s} ║ "
                f"{lk.execution_mode.name:<19s} ║"
            )
        lines.append("╚═════════╩═════════════╩═══════════════╩═════════════════════╝")
        return "\n".join(lines)
