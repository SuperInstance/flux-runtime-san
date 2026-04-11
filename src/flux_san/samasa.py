"""
Samāsa — Sanskrit Compound Word Parser / Type Composer
========================================================

Sanskrit's samāsa (compound) system maps naturally to algebraic type composition:

  Samāsa Type           Sanskrit         Type Theory
  ───────────────────────────────────────────────────────
  द्वन्द्व (dvandva)      → dvandva       → tuple / union type
  कर्मधारय (karmadhāraya) → karmadhāraya  → intersection / product type
  बहुव्रीहि (bahuvrīhi)   → bahuvrīhi     → dependent / existential type

From Pāṇini's Aṣṭādhyāyī:
  samāsāḥ dvandva-karmadhāraya-bahuvrīhi-bhedāḥ
  "Compounds are of three kinds: dvandva, karmadhāraya, bahuvrīhi"
"""

from __future__ import annotations

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any


class SamasaType(IntEnum):
    """The three primary samāsa (compound) types of Sanskrit."""
    DVANDVA      = 1  # द्वन्द्व       — Coordinate → Tuple/Union
    KARMADHARAYA = 2  # कर्मधारय    — Determinative → Intersection/Product
    BAHUVRIHI    = 3  # बहुव्रीहि     — Possessive → Dependent/Existential

    @property
    def devanagari(self) -> str:
        return _DEVANAGARI[self]

    @property
    def iast(self) -> str:
        return _IAST[self]

    @property
    def english(self) -> str:
        return _ENGLISH[self]

    @property
    def type_theory(self) -> str:
        return _TYPE_THEORY[self]


_DEVANAGARI: dict[SamasaType, str] = {
    SamasaType.DVANDVA:      "द्वन्द्व",
    SamasaType.KARMADHARAYA: "कर्मधारय",
    SamasaType.BAHUVRIHI:    "बहुव्रीहि",
}

_IAST: dict[SamasaType, str] = {
    SamasaType.DVANDVA:      "dvandva",
    SamasaType.KARMADHARAYA: "karmadhāraya",
    SamasaType.BAHUVRIHI:    "bahuvrīhi",
}

_ENGLISH: dict[SamasaType, str] = {
    SamasaType.DVANDVA:      "coordinate",
    SamasaType.KARMADHARAYA: "determinative",
    SamasaType.BAHUVRIHI:    "possessive",
}

_TYPE_THEORY: dict[SamasaType, str] = {
    SamasaType.DVANDVA:      "Tuple[A, B] | Union[A, B]",
    SamasaType.KARMADHARAYA: "A & B (intersection / product)",
    SamasaType.BAHUVRIHI:    "∃x. P(x) (dependent / existential)",
}


@dataclass
class Compound:
    """
    A parsed samāsa compound with its components and semantic type.
    """
    word: str                    # The compound word (IAST)
    samasa_type: SamasaType
    components: list[str]        # Constituent words (before sandhi)
    meaning: str = ""            # Resolved meaning
    type_expr: str = ""          # Type expression

    @property
    def arity(self) -> int:
        """Number of components in the compound."""
        return len(self.components)

    @property
    def is_binary(self) -> bool:
        """True if exactly 2 components (dvivacana / dual)."""
        return self.arity == 2

    def __repr__(self) -> str:
        comps = " + ".join(self.components)
        return f"Compound({self.word}, {self.samasa_type.iast}, [{comps}])"


@dataclass
class TypeComposition:
    """
    Represents a type built through samāsa composition.
    Maps Sanskrit compound structure to type-theoretic constructs.
    """
    samasa_type: SamasaType
    left_type: str
    right_type: str
    composed_type: str = ""

    def __post_init__(self):
        if not self.composed_type:
            self.composed_type = self._compose()

    def _compose(self) -> str:
        match self.samasa_type:
            case SamasaType.DVANDVA:
                return f"Tuple[{self.left_type}, {self.right_type}]"
            case SamasaType.KARMADHARAYA:
                return f"Intersection[{self.left_type}, {self.right_type}]"
            case SamasaType.BAHUVRIHI:
                return f"Dependent[∃x: {self.left_type}. {self.right_type}]"
            case _:
                return f"Unknown[{self.left_type}, {self.right_type}]"

    def __repr__(self) -> str:
        return f"TypeComposition({self.composed_type})"


class SamasaParser:
    """
    Parses Sanskrit compound words (samāsa) and maps them to type compositions.

    Supports:
      - Sandhi splitting to recover component words
      - Samāsa type classification (dvandva, karmadhāraya, bahuvrīhi)
      - Type expression generation
    """

    # Coordinate conjunction markers (dvandva signals)
    _dvandva_markers = ["ca", "eva", "vā", "uta"]
    # Adjective-noun patterns (karmadhāraya signals)
    _karmadhara_markers = ["rūpa", "svarūpa", "ākāra"]
    # Possessive markers (bahuvrīhi signals)
    _bahuvrihi_markers = ["vat", "mat", "in", "iṣṭa"]

    # Known compound → components mapping (before sandhi)
    _known_compounds: dict[str, tuple[SamasaType, list[str], str]] = {
        # Mathematical compounds
        "guṇayogaḥ":  (SamasaType.KARMADHARAYA, ["guṇa", "yogaḥ"],    "multiplication"),
        "bhāgahāraḥ": (SamasaType.KARMADHARAYA, ["bhāga", "hāraḥ"],   "division"),
        "rāśiyogaḥ":  (SamasaType.KARMADHARAYA, ["rāśi", "yogaḥ"],    "sum"),
        "śeṣaḥ":     (SamasaType.BAHUVRIHI,    ["śeṣa"],              "remainder"),
        "miśraḥ":     (SamasaType.DVANDVA,      ["miśra"],             "mixed/addition"),
        "pṛthakḥ":    (SamasaType.DVANDVA,      ["pṛthak"],            "separate/difference"),
        "vargaḥ":     (SamasaType.KARMADHARAYA, ["varga"],              "square/power"),
        "mūlaḥ":      (SamasaType.KARMADHARAYA, ["mūla"],               "square root"),
        # Agent compounds
        "kāryasādhakaḥ": (SamasaType.KARMADHARAYA, ["kārya", "sādhakaḥ"], "task-doer"),
        "jñānadātā":     (SamasaType.BAHUVRIHI,    ["jñāna", "dātā"],     "knowledge-giver"),
    }

    @classmethod
    def parse(cls, word: str) -> Compound | None:
        """
        Attempt to parse a compound word.
        Checks known compounds first, then applies heuristic rules.
        """
        # Check known compounds
        if word in cls._known_compounds:
            stype, components, meaning = cls._known_compounds[word]
            return Compound(
                word=word,
                samasa_type=stype,
                components=components,
                meaning=meaning,
                type_expr=TypeComposition(stype, components[0], components[-1] if len(components) > 1 else "⊤").composed_type,
            )

        # Heuristic: check for dvandva markers
        for marker in cls._dvandva_markers:
            if marker in word:
                parts = word.split(marker)
                if len(parts) == 2:
                    return Compound(
                        word=word,
                        samasa_type=SamasaType.DVANDVA,
                        components=parts,
                        meaning=f"({parts[0]} and {parts[1]})",
                        type_expr=f"Tuple[{parts[0]}, {parts[1]}]",
                    )

        # Heuristic: check for bahuvrīhi suffix
        for marker in cls._bahuvrihi_markers:
            if word.endswith(marker):
                stem = word[: -len(marker)]
                return Compound(
                    word=word,
                    samasa_type=SamasaType.BAHUVRIHI,
                    components=[stem],
                    meaning=f"possessing {stem}",
                    type_expr=f"Dependent[∃x: {stem}. P(x)]",
                )

        return None

    @classmethod
    def compose_types(cls, left: str, right: str, samasa_type: SamasaType) -> TypeComposition:
        """Create a type composition from two type expressions."""
        return TypeComposition(samasa_type=samasa_type, left_type=left, right_type=right)

    @classmethod
    def split_sandhi_simple(cls, compound: str) -> list[str]:
        """
        Simple sandhi splitting — reverses common vowel sandhi patterns.
        This is a simplified implementation; full sandhi resolution requires
        Pāṇini's paribhāṣā rules.

        Handles:
          - a + a → ā (e.g., deva + aśva → devāśva → [deva, aśva])
          - i + a → ya (e.g., śakti + a → śaktya → [śakti, a])
          - visarga sandhi (aḥ → ar/ass/s)
        """
        # Known sandhi patterns → splits
        sandhi_rules: list[tuple[str, list[str]]] = [
            # Vowel sandhi (a + a → ā)
            ("ā", ["a", "a"]),
            # Vowel sandhi (i/ī + a → ya)
            ("ya", ["i", "a"]),
            # Vowel sandhi (u/ū + a → va/ava)
            ("va", ["u", "a"]),
            # Visarga sandhi (aḥ before vowel → ar)
            ("ar", ["aḥ", ""]),
            # Visarga sandhi (aḥ before sibilant → ass)
            ("ass", ["aḥ", ""]),
        ]

        results: list[str] = [compound]

        for pattern, replacement in sandhi_rules:
            new_results = []
            for word in results:
                if pattern in word:
                    # Simple split at first occurrence
                    idx = word.find(pattern)
                    if idx > 0:
                        before = word[:idx]
                        after = word[idx + len(pattern):]
                        if after:
                            new_results.extend([before + r + after if r else before
                                               for r in replacement])
                        else:
                            new_results.extend([before + r for r in replacement if r])
                    else:
                        new_results.append(word)
                else:
                    new_results.append(word)
            results = new_results

        return results if len(results) > 1 else [compound]

    @classmethod
    def all_samasa_table(cls) -> str:
        """Pretty-print the samāsa→type composition mapping table."""
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║  Samāsa — Compound Type System                              ║",
            "║  समासाः → Type Composition                                   ║",
            "╠═══════════════════════╦══════════════════════════════════════╣",
            "║  Sanskrit             ║ Type Theory Mapping                 ║",
            "╠═══════════════════════╬══════════════════════════════════════╣",
        ]
        for st in SamasaType:
            lines.append(
                f"║  {st.devanagari:<21s} ║ {st.type_theory:<35s} ║"
            )
        lines.append("╠═══════════════════════╬══════════════════════════════════════╣")
        lines.append("║  Examples:            ║                                    ║")
        lines.append("║  rāśiyogaḥ (sum)      ║ Intersection[rāśi, yogaḥ]         ║")
        lines.append("║  guṇayogaḥ (product)  ║ Intersection[guṇa, yogaḥ]         ║")
        lines.append("║  a+ca (and-combined)  ║ Tuple[a, c]                       ║")
        lines.append("╚═══════════════════════╩══════════════════════════════════════╝")
        return "\n".join(lines)
