"""
Aṣṭau-vibhakti — The Eight-Case Scope System
================================================

Sanskrit's 8 cases (vibhaktayaḥ) map to 8 scope levels in the FLUX runtime.
Each case determines how a noun-phrase accesses bytecode, registers, or memory.

  Vibhakti              Sanskrit       Scope
  ─────────────────────────────────────────────────────────
  1. प्रथमा (nominative)  → public scope         — uncontrolled read access
  2. द्वितीया (accusative)  → object scope        — receives action / argument passing
  3. तृतीया (instrumental) → function/method scope — called as tool/instrument
  4. चतुर्थी (dative)      → capability-granting  — receiving permission
  5. पञ्चमी (ablative)     → origin/derivation   — exporting / source
  6. षष्ठी (genitive)      → ownership scope     — property access / containment
  7. सप्तमी (locative)     → context scope       — in-context / within-region
  8. सम्बोधन (vocative)    → invocation scope    — A2A agent-to-agent call
"""

from __future__ import annotations

from enum import IntEnum
from dataclasses import dataclass, field


class Vibhakti(IntEnum):
    """Aṣṭau-vibhakti — the 8 grammatical cases of Sanskrit as scope levels."""
    PRATHAMA   = 1  # प्रथमा   — Nominative  — public scope
    DVITIYA    = 2  # द्वितीया  — Accusative  — object scope
    TRITIYA    = 3  # तृतीया   — Instrumental — function/method scope
    CHATURTHI  = 4  # चतुर्थी  — Dative      — capability-granting scope
    PANCHAMI   = 5  # पञ्चमी   — Ablative    — origin/derivation scope
    SHASHTHI   = 6  # षष्ठी    — Genitive    — ownership scope
    SAPTAMI    = 7  # सप्तमी   — Locative    — context scope
    SAMBODHANA = 8  # सम्बोधन  — Vocative    — invocation / A2A scope

    @property
    def devanagari(self) -> str:
        """Return the case name in Devanāgarī."""
        return _DEVANAGARI_NAMES[self]

    @property
    def iast(self) -> str:
        """Return the case name in IAST transliteration."""
        return _IAST_NAMES[self]

    @property
    def english(self) -> str:
        """Return the English grammatical term."""
        return _ENGLISH_NAMES[self]

    @property
    def scope(self) -> ScopeLevel:
        """Return the corresponding FLUX scope level."""
        return _VIBHAKTI_TO_SCOPE[self]


class ScopeLevel(IntEnum):
    """FLUX bytecode access pattern for each scope."""
    PUBLIC       = 0  # Uncontrolled read access
    OBJECT       = 1  # Argument passing / receives action
    FUNCTION     = 2  # Called as instrument
    CAPABILITY   = 3  # Permission grant
    ORIGIN       = 4  # Export / source
    OWNERSHIP    = 5  # Property / containment
    CONTEXT      = 6  # In-context / within-region
    INVOCATION   = 7  # A2A agent-to-agent


# Lookup tables
_DEVANAGARI_NAMES: dict[Vibhakti, str] = {
    Vibhakti.PRATHAMA:   "प्रथमा",
    Vibhakti.DVITIYA:    "द्वितीया",
    Vibhakti.TRITIYA:    "तृतीया",
    Vibhakti.CHATURTHI:  "चतुर्थी",
    Vibhakti.PANCHAMI:   "पञ्चमी",
    Vibhakti.SHASHTHI:   "षष्ठी",
    Vibhakti.SAPTAMI:    "सप्तमी",
    Vibhakti.SAMBODHANA: "सम्बोधन",
}

_IAST_NAMES: dict[Vibhakti, str] = {
    Vibhakti.PRATHAMA:   "prathamā",
    Vibhakti.DVITIYA:    "dvitīyā",
    Vibhakti.TRITIYA:    "tṛtīyā",
    Vibhakti.CHATURTHI:  "caturthī",
    Vibhakti.PANCHAMI:   "pañcamī",
    Vibhakti.SHASHTHI:   "ṣaṣṭhī",
    Vibhakti.SAPTAMI:    "saptamī",
    Vibhakti.SAMBODHANA: "sambodhana",
}

_ENGLISH_NAMES: dict[Vibhakti, str] = {
    Vibhakti.PRATHAMA:   "nominative",
    Vibhakti.DVITIYA:    "accusative",
    Vibhakti.TRITIYA:    "instrumental",
    Vibhakti.CHATURTHI:  "dative",
    Vibhakti.PANCHAMI:   "ablative",
    Vibhakti.SHASHTHI:   "genitive",
    Vibhakti.SAPTAMI:    "locative",
    Vibhakti.SAMBODHANA: "vocative",
}

_VIBHAKTI_TO_SCOPE: dict[Vibhakti, ScopeLevel] = {
    Vibhakti.PRATHAMA:   ScopeLevel.PUBLIC,
    Vibhakti.DVITIYA:    ScopeLevel.OBJECT,
    Vibhakti.TRITIYA:    ScopeLevel.FUNCTION,
    Vibhakti.CHATURTHI:  ScopeLevel.CAPABILITY,
    Vibhakti.PANCHAMI:   ScopeLevel.ORIGIN,
    Vibhakti.SHASHTHI:   ScopeLevel.OWNERSHIP,
    Vibhakti.SAPTAMI:    ScopeLevel.CONTEXT,
    Vibhakti.SAMBODHANA: ScopeLevel.INVOCATION,
}

# Case terminations (śabda-rūpāṇi) for masculine a-stem (rāma)
# These are the suffix patterns used to detect vibhakti from inflected forms.
CASE_TERMINATIONS_ASTEM: dict[Vibhakti, list[str]] = {
    # Singular (ekavacana)
    Vibhakti.PRATHAMA:   ["aḥ", "ः"],
    Vibhakti.DVITIYA:    ["am", "म्"],
    Vibhakti.TRITIYA:    ["eṇa", "ेण"],
    Vibhakti.CHATURTHI:  ["āya", "ाय"],
    Vibhakti.PANCHAMI:   ["āt", "ात्"],
    Vibhakti.SHASHTHI:   ["asya", "स्य"],
    Vibhakti.SAPTAMI:    ["e", "े"],
    Vibhakti.SAMBODHANA: ["a", ""],
}


@dataclass
class ScopedAccess:
    """
    Represents a memory/register access qualified by a vibhakti scope.
    The scope level determines the bytecode pattern generated for the access.
    """
    register: int
    vibhakti: Vibhakti
    offset: int = 0
    region: int = 0

    @property
    def scope_level(self) -> ScopeLevel:
        return self.vibhakti.scope

    @property
    def access_pattern(self) -> str:
        """
        Return the bytecode access pattern for this scoped access.
        Different vibhaktis compile to different instruction sequences.
        """
        patterns = {
            ScopeLevel.PUBLIC:     f"MOV   R0, R{self.register}",
            ScopeLevel.OBJECT:     f"LOAD  R0, R{self.register}",
            ScopeLevel.FUNCTION:   f"CALL  R{self.register}",
            ScopeLevel.CAPABILITY: f"CAP_REQ R0, R{self.register}",
            ScopeLevel.ORIGIN:     f"STORE R{self.register}, R0",
            ScopeLevel.OWNERSHIP:  f"IOR   R0, R{self.register}",
            ScopeLevel.CONTEXT:    f"REGION_ENTER {self.region}; MOV R0, R{self.register}",
            ScopeLevel.INVOCATION: f"TELL  R{self.register}",
        }
        return patterns.get(self.scope_level, "NOP")

    def __repr__(self) -> str:
        return (
            f"ScopedAccess(R{self.register}, "
            f"{self.vibhakti.devanagari}/{self.vibhakti.iast}, "
            f"scope={self.scope_level.name})"
        )


class VibhaktiValidator:
    """
    Validates and resolves vibhakti (case) for inflected Sanskrit noun phrases.
    Maps terminal suffixes to grammatical cases using Pāṇinian rules.
    """

    # Common IAST terminations → Vibhakti mapping (simplified)
    _termination_map: list[tuple[list[str], Vibhakti]] = [
        (["aḥ"],                    Vibhakti.PRATHAMA),
        (["am"],                     Vibhakti.DVITIYA),
        (["eṇa", "iṇā", "ina"],     Vibhakti.TRITIYA),
        (["āya", "e", "āyaḥ"],       Vibhakti.CHATURTHI),
        (["āt", "as", "oḥ"],        Vibhakti.PANCHAMI),
        (["asya", "iḥ", "oḥ"],      Vibhakti.SHASHTHI),
        (["e", "i", "ām", "āni"],    Vibhakti.SAPTAMI),
        (["he", "ho", "a"],          Vibhakti.SAMBODHANA),
    ]

    @classmethod
    def detect_vibhakti(cls, word: str) -> Vibhakti | None:
        """
        Attempt to detect the vibhakti of a Sanskrit word from its IAST ending.
        Returns None if the termination is ambiguous or unrecognized.
        """
        for terminations, vibhakti in cls._termination_map:
            for term in terminations:
                if word.endswith(term):
                    return vibhakti
        return None

    @classmethod
    def scope_for_access(cls, word: str, register: int) -> ScopedAccess | None:
        """Create a ScopedAccess by detecting the vibhakti of a word."""
        vibhakti = cls.detect_vibhakti(word)
        if vibhakti is None:
            return None
        return ScopedAccess(register=register, vibhakti=vibhakti)

    @classmethod
    def all_cases_table(cls) -> str:
        """Pretty-print the complete vibhakti→scope mapping table."""
        lines = [
            "╔═══════════════════════════════════════════════════════════════╗",
            "║  Aṣṭau-vibhakti — Eight-Case Scope System                  ║",
            "║  पाणिनेः व्याकरणम् → FLUX Scope Levels                      ║",
            "╠═════════╦══════════════╦═══════════════╦═════════════════════╣",
            "║  Case   ║ Sanskrit    ║ English       ║ FLUX Scope         ║",
            "╠═════════╬══════════════╬═══════════════╬═════════════════════╣",
        ]
        for v in Vibhakti:
            lines.append(
                f"║  {v.value:>2}     ║ {v.devanagari:<12s} ║ {v.english:<13s} ║ {v.scope.name:<19s} ║"
            )
        lines.append("╚═════════╩══════════════╩═══════════════╩═════════════════════╝")
        return "\n".join(lines)
