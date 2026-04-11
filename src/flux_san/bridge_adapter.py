"""
FLUX-SAN Bridge Adapter — विभक्ति/लकार Bridge Adapter

Exposes the Sanskrit vibhakti (8-case scope system) and lakāra
(8 execution mode system) to the A2A type-safe cross-language bridge.

Sanskrit's rich morphological system provides:
  अष्टौ विभक्तयः (8 cases) → 8 scope levels
  अष्टौ लकाराः (8 tenses/moods) → 8 execution modes

Interface:
    adapter = SanBridgeAdapter()
    types = adapter.export_types()
    local = adapter.import_type(universal)
    cost = adapter.bridge_cost("lat")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from flux_san.vibhakti import Vibhakti, ScopeLevel
from flux_san.lakara import Lakara, ExecutionMode


# ══════════════════════════════════════════════════════════════════════
# Common bridge types
# ══════════════════════════════════════════════════════════════════════

@dataclass
class BridgeCost:
    numeric_cost: float
    information_loss: list[str] = field(default_factory=list)
    ambiguity_warnings: list[str] = field(default_factory=list)


@dataclass
class UniversalType:
    paradigm: str
    category: str
    constraints: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class BridgeAdapter(ABC):
    @abstractmethod
    def export_types(self) -> list[UniversalType]: ...

    @abstractmethod
    def import_type(self, universal: UniversalType) -> Any: ...

    @abstractmethod
    def bridge_cost(self, target_lang: str) -> BridgeCost: ...


# ══════════════════════════════════════════════════════════════════════
# Purusha (Person) and Vacana (Number) — defined here for bridge use
# ══════════════════════════════════════════════════════════════════════

class Purusha(IntEnum):
    """त्रयः पुरुषाः — the 3 persons of Sanskrit verbs."""
    PRATHAMA  = 1  # Third person (प्रथमपुरुष) — he/she/it/they
    MADHYAMA  = 2  # Second person (मध्यमपुरुष) — you
    UTTAMA    = 3  # First person (उत्तमपुरुष) — I/we


class Vacana(IntEnum):
    """द्वि वचनम् — the 2 numbers of Sanskrit."""
    EKAVACHANA = 1  # Singular (एकवचनम्)
    DVIVACHANA = 2  # Plural (द्विवचनम्)


# ══════════════════════════════════════════════════════════════════════
# SanTypeSignature — Sanskrit type representation
# ══════════════════════════════════════════════════════════════════════

@dataclass
class SanTypeSignature:
    """Represents a Sanskrit type for bridge export/import.

    Sanskrit's morphological richness provides a four-dimensional type:
      - vibhakti: grammatical case (8 cases → 8 scope levels)
      - lakara: tense/mood (8 lakāras → 8 execution modes)
      - purusha: person (3 persons → subject identity)
      - vacana: number (singular/plural)

    Attributes:
        vibhakti: grammatical case (scope role)
        lakara: tense/mood (execution mode)
        purusha: person (subject identity)
        vacana: number (singular/plural)
    """
    vibhakti: Vibhakti = Vibhakti.PRATHAMA
    lakara: Lakara = Lakara.LAT
    purusha: Purusha = Purusha.PRATHAMA
    vacana: Vacana = Vacana.EKAVACHANA

    @property
    def scope_level(self) -> ScopeLevel:
        return self.vibhakti.scope

    @property
    def execution_mode(self) -> ExecutionMode:
        return self.lakara.execution_mode

    @property
    def vibhakti_name(self) -> str:
        return f"{self.vibhakti.devanagari} ({self.vibhakti.english})"

    @property
    def lakara_name(self) -> str:
        return f"{self.lakara.devanagari} ({self.lakara.english})"


# ══════════════════════════════════════════════════════════════════════
# Vibhakti → Universal Type Mapping (8 cases → universal roles)
# ══════════════════════════════════════════════════════════════════════

_VIBHAKTI_TO_UNIVERSAL: dict[Vibhakti, tuple[str, str, float]] = {
    Vibhakti.PRATHAMA:   ("Agent",     "Subject / public scope — uncontrolled read", 0.95),
    Vibhakti.DVITIYA:    ("Patient",   "Direct object / receives action", 0.95),
    Vibhakti.TRITIYA:    ("Instrument", "Tool / instrument / function call", 0.95),
    Vibhakti.CHATURTHI:  ("Recipient", "Dative / capability grant / permission", 0.95),
    Vibhakti.PANCHAMI:   ("Source",    "Ablative / origin / export / derivation", 0.95),
    Vibhakti.SHASHTHI:   ("Possessor", "Genitive / ownership / containment", 0.95),
    Vibhakti.SAPTAMI:    ("Context",   "Locative / in-context / within-region", 0.95),
    Vibhakti.SAMBODHANA: ("Invocant",  "Vocative / invocation / A2A call", 0.95),
}

# Lakāra → Universal Temporal/Execution Mode Mapping
_LAKARA_TO_UNIVERSAL: dict[Lakara, tuple[str, str, float]] = {
    Lakara.LAT:       ("Present",    "Present — normal execution", 0.95),
    Lakara.LAN:       ("Past",       "Imperfect — conditional/branch execution", 0.95),
    Lakara.LIT:       ("Verified",   "Perfect — verified/cached execution", 0.95),
    Lakara.LUN:       ("Immediate",  "Aorist — immediate/atomic execution", 0.95),
    Lakara.LRIT:      ("Future",     "Future — deferred/lazy execution", 0.95),
    Lakara.LRUNG:     ("Conditional","Conditional — speculative execution", 0.90),
    Lakara.VIDHILING: ("Potential",  "Potential — speculative execution", 0.90),
    Lakara.ASIRLING:  ("Imperative", "Imperative — forced execution", 0.95),
}

# Reverse maps
_UNIVERSAL_TO_VIBHAKTI: dict[str, Vibhakti] = {
    "Agent":     Vibhakti.PRATHAMA,
    "Patient":   Vibhakti.DVITIYA,
    "Instrument": Vibhakti.TRITIYA,
    "Recipient": Vibhakti.CHATURTHI,
    "Source":    Vibhakti.PANCHAMI,
    "Possessor": Vibhakti.SHASHTHI,
    "Context":   Vibhakti.SAPTAMI,
    "Invocant":  Vibhakti.SAMBODHANA,
}

_UNIVERSAL_TO_LAKARA: dict[str, Lakara] = {
    "Present":    Lakara.LAT,
    "Past":       Lakara.LAN,
    "Verified":   Lakara.LIT,
    "Immediate":  Lakara.LUN,
    "Future":     Lakara.LRIT,
    "Conditional": Lakara.LRUNG,
    "Potential":  Lakara.VIDHILING,
    "Imperative": Lakara.ASIRLING,
}


# ══════════════════════════════════════════════════════════════════════
# Language affinity
# ══════════════════════════════════════════════════════════════════════

_LANG_AFFINITY: dict[str, dict[str, Any]] = {
    "san": {"cost": 0.0, "loss": [], "ambiguity": []},
    "lat": {"cost": 0.15, "loss": ["2 extra vibhakti (Sanskrit has 8, Latin has 6)",
            "2 extra lakāra distinctions"],
            "ambiguity": ["Latin 6 cases compress 8 vibhakti; 4 moods compress 8 lakāras"]},
    "deu": {"cost": 0.40, "loss": ["4 extra vibhakti (German has 4, Sanskrit 8)",
            "No lakāra equivalent in German"],
            "ambiguity": ["German 4 Kasus compress 8 vibhakti significantly"]},
    "zho": {"cost": 0.60, "loss": ["All vibhakti scope distinctions",
            "All lakāra temporal modes", "Person/number system"],
            "ambiguity": ["Chinese has no case inflection — all roles via word order/particles"]},
    "kor": {"cost": 0.50, "loss": ["Vibhakti scope levels",
            "Lakāra temporal distinctions"],
            "ambiguity": ["Korean particles partially overlap with vibhakti roles"]},
    "wen": {"cost": 0.65, "loss": ["All inflectional morphology",
            "All case/tense distinctions"],
            "ambiguity": ["Classical Chinese is analytic — no inflection at all"]},
}


# ══════════════════════════════════════════════════════════════════════
# SanBridgeAdapter
# ══════════════════════════════════════════════════════════════════════

class SanBridgeAdapter(BridgeAdapter):
    """Bridge adapter for the Sanskrit (संस्कृतम्) vibhakti/lakāra system.

    Exports all 8 vibhakti (cases/scope levels) and 8 lakāra
    (tenses/execution modes) as UniversalType instances.

    Usage:
        adapter = SanBridgeAdapter()
        types = adapter.export_types()
        cost = adapter.bridge_cost("lat")
    """

    PARADIGM = "san"

    def export_types(self) -> list[UniversalType]:
        """Export all Sanskrit vibhakti and lakāra types.

        Returns:
            List of UniversalType covering:
            - 8 vibhakti (scope roles)
            - 8 lakāra (execution/temporal modes)
        """
        exported: list[UniversalType] = []

        # Export vibhakti types
        for vibhakti, (cat, desc, conf) in _VIBHAKTI_TO_UNIVERSAL.items():
            exported.append(UniversalType(
                paradigm=self.PARADIGM,
                category=cat,
                constraints={
                    "vibhakti": vibhakti.name,
                    "devanagari": vibhakti.devanagari,
                    "iast": vibhakti.iast,
                    "english": vibhakti.english,
                    "scope": vibhakti.scope.name,
                    "description": desc,
                    "type_kind": "vibhakti_role",
                },
                confidence=conf,
            ))

        # Export lakāra types
        for lakara, (cat, desc, conf) in _LAKARA_TO_UNIVERSAL.items():
            exported.append(UniversalType(
                paradigm=self.PARADIGM,
                category=cat,
                constraints={
                    "lakara": lakara.name,
                    "devanagari": lakara.devanagari,
                    "iast": lakara.iast,
                    "english": lakara.english,
                    "execution_mode": lakara.execution_mode.name,
                    "description": desc,
                    "type_kind": "lakara_mode",
                },
                confidence=conf,
            ))

        return exported

    def import_type(self, universal: UniversalType) -> SanTypeSignature:
        """Import a universal type into the Sanskrit vibhakti/lakāra system.

        Args:
            universal: A UniversalType from another runtime

        Returns:
            SanTypeSignature with best-matching vibhakti and lakāra
        """
        category = universal.category
        constraints = universal.constraints

        # Resolve vibhakti from category
        vibhakti = _UNIVERSAL_TO_VIBHAKTI.get(category)

        # Check constraints for explicit vibhakti
        if vibhakti is None and "vibhakti" in constraints:
            for v in Vibhakti:
                if v.name == constraints["vibhakti"]:
                    vibhakti = v
                    break

        if vibhakti is None:
            vibhakti = Vibhakti.PRATHAMA

        # Resolve lakāra from category (temporal categories)
        lakara = _UNIVERSAL_TO_LAKARA.get(category)

        # Check constraints for explicit lakāra
        if lakara is None and "lakara" in constraints:
            for lk in Lakara:
                if lk.name == constraints["lakara"]:
                    lakara = lk
                    break

        if lakara is None:
            lakara = Lakara.LAT

        # Resolve purusha from constraints
        purusha = Purusha.PRATHAMA
        if "purusha" in constraints:
            for p in Purusha:
                if p.name.lower() == constraints["purusha"].lower():
                    purusha = p

        # Resolve vacana from constraints
        vacana = Vacana.EKAVACHANA
        if "vacana" in constraints:
            for v in Vacana:
                if v.name.lower() == constraints["vacana"].lower():
                    vacana = v

        return SanTypeSignature(
            vibhakti=vibhakti,
            lakara=lakara,
            purusha=purusha,
            vacana=vacana,
        )

    def bridge_cost(self, target_lang: str) -> BridgeCost:
        """Estimate bridge cost to another runtime.

        Args:
            target_lang: Target language code

        Returns:
            BridgeCost with estimated difficulty
        """
        target = target_lang.lower().strip()

        if target == self.PARADIGM:
            return BridgeCost(numeric_cost=0.0)

        affinity = _LANG_AFFINITY.get(target, {
            "cost": 0.7,
            "loss": ["All morphological distinctions"],
            "ambiguity": ["Unknown target language"],
        })

        return BridgeCost(
            numeric_cost=affinity["cost"],
            information_loss=list(affinity["loss"]),
            ambiguity_warnings=list(affinity["ambiguity"]),
        )

    def detect_vibhakti(self, word: str) -> SanTypeSignature | None:
        """Detect vibhakti from a Sanskrit word ending.

        Args:
            word: Sanskrit word in IAST transliteration

        Returns:
            SanTypeSignature if vibhakti detected, None otherwise
        """
        from flux_san.vibhakti import VibhaktiValidator

        detected = VibhaktiValidator.detect_vibhakti(word)
        if detected is None:
            return None

        return SanTypeSignature(
            vibhakti=detected,
            lakara=Lakara.LAT,
            purusha=Purusha.PRATHAMA,
            vacana=Vacana.EKAVACHANA,
        )
