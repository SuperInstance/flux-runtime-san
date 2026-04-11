"""
Vocabulary — Sanskrit Vocabulary Tiling System
===============================================

Sanskrit's morphological productivity is organized into 4 abstraction levels.
Each level maps morphological patterns to FLUX bytecode assembly templates.
The vocabulary system provides the "lexicon" that the sandhi tokenizer and
dhatu compiler use to convert natural language into bytecode.

Levels:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Level 0: Dhātu-prayoga (धातुप्रयोगः)                                │
  │  Single verbal root → single opcode                                     │
  │  e.g., √bhū → NOP, √gam → JMP, √yuj → IADD                            │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  Level 1: Kṛdanta (कृदन्तम्)                                         │
  │  Verbal root + suffix → compound operation                              │
  │  e.g., gaṇaya-ti (compute + 3sg) → IADD R0, R1, R2                    │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  Level 2: Taddhita (तद्धितम्)                                         │
  │  Secondary derivation → domain-specific vocabularies                    │
  │  e.g., rāśi-yoga-śeṣa (quantity-sum-remainder) → IMOD                 │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  Level 3: Samāsa (समासः)                                              │
  │  Compound words → multi-step computation tiles                          │
  │  e.g., rāśi-guṇayogaḥ (quantity-product) → IMUL then STORE             │
  └─────────────────────────────────────────────────────────────────────────┘

From Pāṇini's Aṣṭādhyāyī:
  kṛdantaḥ kṛt-pratyaya-antaḥ — "kṛdanta: ending in a kṛt suffix"
  taddhitaḥ tad-pratyaya-antaḥ — "taddhita: ending in a taddhita suffix"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from flux_san.vm import Opcode
from flux_san.dhatu import DhatuCompiler, Dhatu, Gana, Pada
from flux_san.samasa import SamasaType, SamasaParser, Compound


# ---------------------------------------------------------------------------
# Vocabulary levels
# ---------------------------------------------------------------------------

class VocabLevel(IntEnum):
    """The 4 abstraction levels of the Sanskrit vocabulary system."""
    DHATU_PRAYOGA = 0   # धातुप्रयोगः  — root application
    KRDANTA       = 1   # कृदन्तम्     — primary derivation
    TADDHITA      = 2   # तद्धितम्     — secondary derivation
    SAMASA        = 3   # समासः        — compound / tile


# ---------------------------------------------------------------------------
# Vocabulary tile — a reusable bytecode assembly template
# ---------------------------------------------------------------------------

@dataclass
class VocabTile:
    """A reusable bytecode assembly template mapped from a Sanskrit morphological pattern.

    A tile encapsulates:
      - pattern: The Sanskrit surface form (regex for matching)
      - level: The vocabulary abstraction level
      - bytecode_template: A callable that generates bytecode given operands
      - description: Human-readable explanation
      - required_operands: Number of register/immediate arguments needed
      - examples: Example usages with expected results
    """
    pattern: str                          # Regex pattern for matching
    level: VocabLevel
    bytecode_fn: Any                      # Callable: (*operands) → bytearray
    name: str = ""                        # Tile name
    description: str = ""                 # Description
    sanskrit_name: str = ""               # Name in Devanāgarī
    required_operands: int = 2            # Number of expected operands
    operand_types: list[str] = field(default_factory=lambda: ["register"])
    examples: list[tuple[str, list[int], str]] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        """Check if *text* matches this tile's pattern."""
        return bool(re.search(self.pattern, text, re.IGNORECASE))

    def compile(self, *operands: int) -> bytearray:
        """Generate bytecode for this tile with given operands."""
        return self.bytecode_fn(*operands)

    def describe(self) -> str:
        """Return a formatted description."""
        return (
            f"[L{self.level}] {self.name or self.pattern} "
            f"({self.description}) — needs {self.required_operands} operands"
        )


# ---------------------------------------------------------------------------
# Vocabulary table — the complete tile registry
# ---------------------------------------------------------------------------

class VocabularyTable:
    """The complete FLUX-san vocabulary registry.

    Organized by abstraction level, the VocabularyTable provides:
      - Pattern matching against Sanskrit surface forms
      - Bytecode generation from matched patterns
      - Tile lookup by level, name, or pattern
      - Domain-specific vocabulary subsets

    Usage::

        vocab = VocabularyTable()

        # Find tiles matching a Sanskrit expression
        tiles = vocab.find("gaṇaya R1 pluta R2")

        # Get a specific tile by name
        tile = vocab.get_tile("addition")
        if tile:
            bc = tile.compile(0, 1, 2)  # IADD R0, R1, R2

        # List all tiles at a given level
        level1_tiles = vocab.by_level(VocabLevel.KRDANTA)
    """

    def __init__(self):
        self._tiles: list[VocabTile] = []
        self._pattern_cache: dict[str, re.Pattern] = {}
        self._dhatu_compiler = DhatuCompiler()
        self._build_levels()

    def _build_levels(self) -> None:
        """Build all vocabulary levels."""
        self._build_level_0()
        self._build_level_1()
        self._build_level_2()
        self._build_level_3()

    # ===================================================================
    # Level 0: Dhātu-prayoga — Root Application
    # Single verbal root → single opcode
    # ===================================================================

    def _build_level_0(self) -> None:
        """Build Level 0 vocabulary: root → opcode mappings.

        Each tile maps a single dhātu to its primary opcode.
        These are the fundamental building blocks — the Sanskrit
        equivalent of machine instructions.
        """
        # √bhū (to be) → NOP / MOV / MOVI
        self._tiles.append(VocabTile(
            pattern=r"\bbhū\b|\bbhavati\b|\bas\b|\bbhavate\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda: bytearray([Opcode.NOP]),
            name="to_be",
            description="√bhū — to be, become, exist → NOP (identity)",
            sanskrit_name="भू / भवति",
            required_operands=0,
        ))

        # √gam (to go) → JMP
        self._tiles.append(VocabTile(
            pattern=r"\bgam\b|\bgacchati\b|\bgacchate\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda addr=0: bytearray([
                Opcode.JMP, addr & 0xFF, (addr >> 8) & 0xFF
            ]),
            name="to_go",
            description="√gam — to go, proceed → JMP (control flow)",
            sanskrit_name="गम् / गच्छति",
            required_operands=1,
            operand_types=["address"],
        ))

        # √sthā (to stand) → HALT
        self._tiles.append(VocabTile(
            pattern=r"\bsthā\b|\btiṣṭhati\b|\bvirāma\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda: bytearray([Opcode.HALT]),
            name="to_stand",
            description="√sthā — to stand, remain → HALT (stop execution)",
            sanskrit_name="स्था / तिष्ठति / विराम",
            required_operands=0,
        ))

        # √kṛ (to do) → CALL
        self._tiles.append(VocabTile(
            pattern=r"\bkṛ\b|\bkaroti\b|\bkarote\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda addr=0: bytearray([
                Opcode.CALL, addr & 0xFF, (addr >> 8) & 0xFF
            ]),
            name="to_do",
            description="√kṛ — to do, make, perform → CALL (function invocation)",
            sanskrit_name="कृ / करोति",
            required_operands=1,
            operand_types=["address"],
        ))

        # √yuj (to join) → IADD
        self._tiles.append(VocabTile(
            pattern=r"\byuj\b|\byunakti\b|\byunkte\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IADD, rd, ra, rb
            ]),
            name="to_join",
            description="√yuj — to join, unite → IADD (arithmetic addition)",
            sanskrit_name="युज् / युनक्ति",
            required_operands=3,
            operand_types=["register", "register", "register"],
        ))

        # √dā (to give) → STORE
        self._tiles.append(VocabTile(
            pattern=r"\bdā\b|\bdadāti\b|\bdadate\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda src=0, dst=0: bytearray([
                Opcode.STORE, src, dst
            ]),
            name="to_give",
            description="√dā — to give, grant → STORE (write to register)",
            sanskrit_name="दा / ददाति",
            required_operands=2,
            operand_types=["register", "register"],
        ))

        # √vid (to know) → LOAD
        self._tiles.append(VocabTile(
            pattern=r"\bvid\b|\bveda\b|\bvindate\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda dst=0, src=0: bytearray([
                Opcode.LOAD, dst, src
            ]),
            name="to_know",
            description="√vid — to know, find → LOAD (read from register)",
            sanskrit_name="विद् / वेद",
            required_operands=2,
            operand_types=["register", "register"],
        ))

        # √hṛ (to take) → POP
        self._tiles.append(VocabTile(
            pattern=r"\bhṛ\b|\bharati\b|\bhṛṇāti\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda r=0: bytearray([Opcode.POP, r]),
            name="to_take",
            description="√hṛ — to take, remove → POP (from stack)",
            sanskrit_name="हृ / हरति",
            required_operands=1,
            operand_types=["register"],
        ))

        # √brū (to speak) → TELL / PRINT
        self._tiles.append(VocabTile(
            pattern=r"\bbrū\b|\bbravīti\b|\bbrūhi\b|\bdarśaya\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda r=0: bytearray([Opcode.PRINT, r]),
            name="to_speak",
            description="√brū — to speak, show → PRINT (output)",
            sanskrit_name="ब्रू / ब्रवीति / दर्शय",
            required_operands=1,
            operand_types=["register"],
        ))

        # √kṣip (to throw) → PUSH
        self._tiles.append(VocabTile(
            pattern=r"\bkṣip\b|\bkṣipati\b|\bjuṣa\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda r=0: bytearray([Opcode.PUSH, r]),
            name="to_throw",
            description="√kṣip — to throw → PUSH (onto stack)",
            sanskrit_name="क्षिप् / क्षिपति / जुष",
            required_operands=1,
            operand_types=["register"],
        ))

        # √adhi-īś (to rule) → TRUST_CHECK
        self._tiles.append(VocabTile(
            pattern=r"\badhiīś\b|\badhiśate\b",
            level=VocabLevel.DHATU_PRAYOGA,
            bytecode_fn=lambda r=0: bytearray([Opcode.TRUST_CHECK, r]),
            name="to_rule",
            description="√adhi-īś — to rule over → TRUST_CHECK",
            sanskrit_name="अधीश् / अधिशते",
            required_operands=1,
            operand_types=["register"],
        ))

    # ===================================================================
    # Level 1: Kṛdanta — Primary Derivation
    # Verbal root + suffix → compound operation
    # ===================================================================

    def _build_level_1(self) -> None:
        """Build Level 1 vocabulary: derived forms → compound operations.

        Kṛdanta words are formed by adding kṛt suffixes to verbal roots.
        The suffix determines the semantic role and the bytecode template.
        """
        # gaṇaya ... pluta ... (compute ... plus ...) → IADD
        self._tiles.append(VocabTile(
            pattern=r"gaṇaya\s+(?P<a>\S+)\s+pluta\s+(?P<b>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IADD, rd, ra, rb
            ]),
            name="addition",
            description="gaṇaya A pluta B → IADD (addition / योगः)",
            sanskrit_name="गणय ... प्लुत ... → योगः",
            required_operands=3,
            operand_types=["register", "register", "register"],
            examples=[
                ("gaṇaya R1 pluta R2", [0, 1, 2], "R0 = R1 + R2"),
            ],
        ))

        # ... guṇa ... (times ...) → IMUL
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+guṇa\s+(?P<b>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IMUL, rd, ra, rb
            ]),
            name="multiplication",
            description="A guṇa B → IMUL (multiplication / गुणनम्)",
            sanskrit_name="... गुण ... → गुणनम्",
            required_operands=3,
            operand_types=["register", "register", "register"],
            examples=[
                ("R1 guṇa R2", [0, 1, 2], "R0 = R1 × R2"),
            ],
        ))

        # ... śoṣa ... (minus ...) → ISUB
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+śoṣa\s+(?P<b>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.ISUB, rd, ra, rb
            ]),
            name="subtraction",
            description="A śoṣa B → ISUB (subtraction / व्यवकलनम्)",
            sanskrit_name="... शोष ... → व्यवकलनम्",
            required_operands=3,
            operand_types=["register", "register", "register"],
            examples=[
                ("R1 śoṣa R2", [0, 1, 2], "R0 = R1 − R2"),
            ],
        ))

        # ... bhāj ... (divided by ...) → IDIV
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+bhāj\s+(?P<b>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IDIV, rd, ra, rb
            ]),
            name="division",
            description="A bhāj B → IDIV (division / भाजनम्)",
            sanskrit_name="... भाज ... → भाजनम्",
            required_operands=3,
            operand_types=["register", "register", "register"],
            examples=[
                ("R1 bhāj R2", [0, 1, 2], "R0 = R1 ÷ R2"),
            ],
        ))

        # ... śeṣa ... (remainder ...) → IMOD
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+śeṣa\s+(?P<b>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IMOD, rd, ra, rb
            ]),
            name="modulo",
            description="A śeṣa B → IMOD (remainder / शेषः)",
            sanskrit_name="... शेष ... → शेषः",
            required_operands=3,
            operand_types=["register", "register", "register"],
        ))

        # ... tulya ... (equal to ...) → CMP
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+tulya\s+(?P<b>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda ra=0, rb=0: bytearray([
                Opcode.ICMP, ra, rb
            ]),
            name="compare",
            description="A tulya B → ICMP (compare / तुलना)",
            sanskrit_name="... तुल्य ... → तुलना",
            required_operands=2,
            operand_types=["register", "register"],
            examples=[
                ("R1 tulya R2", [1, 2], "compare R1, R2 → flags"),
            ],
        ))

        # load ... saha ... (place ... with ...) → MOVI
        self._tiles.append(VocabTile(
            pattern=r"load\s+(?P<reg>\S+)\s+saha\s+(?P<val>-?\d+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda r=0, val=0: (
                lambda _r=r, _v=val: bytearray([
                    Opcode.MOVI, _r, _v & 0xFF, (_v >> 8) & 0xFF
                ])
            )(),
            name="load_immediate",
            description="load Rn saha val → MOVI (load immediate / स्थापनम्)",
            sanskrit_name="लोड् ... सह ... → स्थापनम्",
            required_operands=2,
            operand_types=["register", "immediate"],
        ))

        # pluta ... (increase ...) → INC
        self._tiles.append(VocabTile(
            pattern=r"pluta\s+(?P<r>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda r=0: bytearray([Opcode.INC, r]),
            name="increment",
            description="pluta Rn → INC (increment / वृद्धिः)",
            sanskrit_name="प्लुत ... → वृद्धिः",
            required_operands=1,
            operand_types=["register"],
        ))

        # hrāsa ... (decrease ...) → DEC
        self._tiles.append(VocabTile(
            pattern=r"hrāsa\s+(?P<r>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda r=0: bytearray([Opcode.DEC, r]),
            name="decrement",
            description="hrāsa Rn → DEC (decrement / ह्रासः)",
            sanskrit_name="ह्रास ... → ह्रासः",
            required_operands=1,
            operand_types=["register"],
        ))

        # juṣa ... (push ...) → PUSH
        self._tiles.append(VocabTile(
            pattern=r"juṣa\s+(?P<r>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda r=0: bytearray([Opcode.PUSH, r]),
            name="push_stack",
            description="juṣa Rn → PUSH (stack push / स्तरणम्)",
            sanskrit_name="जुष ... → स्तरणम्",
            required_operands=1,
            operand_types=["register"],
        ))

        # gṛhṇa ... (pop ...) → POP
        self._tiles.append(VocabTile(
            pattern=r"gṛhṇa\s+(?P<r>\S+)",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda r=0: bytearray([Opcode.POP, r]),
            name="pop_stack",
            description="gṛhṇa Rn → POP (stack pop / स्तरोत्तारणम्)",
            sanskrit_name="गृह्ण ... → स्तरोत्तारणम्",
            required_operands=1,
            operand_types=["register"],
        ))

        # ... itaḥ ... paryantayogaḥ (range sum from ... to ...) → loop + IADD
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+itaḥ\s+(?P<b>\S+)\s+paryantayogaḥ",
            level=VocabLevel.KRDANTA,
            bytecode_fn=lambda ra=1, rb=2: bytearray([
                # Gauss formula: R0 = Rb*(Rb+1)/2 - (Ra-1)*Ra/2
                Opcode.MOV, 1, ra,
                Opcode.MOV, 2, rb,
                Opcode.MOV, 3, 1,          # R3 = Ra
                Opcode.DEC, 3,              # R3 = Ra - 1
                Opcode.MOV, 4, 2,          # R4 = Rb
                Opcode.INC, 4,              # R4 = Rb + 1
                Opcode.IMUL, 5, 2, 4,      # R5 = Rb * (Rb + 1)
                Opcode.MOVI, 6, 2, 0,      # R6 = 2
                Opcode.IDIV, 4, 5, 6,      # R4 = R5 / 2
                Opcode.MOV, 5, 3,          # R5 = Ra - 1
                Opcode.INC, 5,              # R5 = Ra
                Opcode.IMUL, 7, 3, 5,      # R7 = (Ra-1) * Ra
                Opcode.IDIV, 5, 7, 6,      # R5 = R7 / 2
                Opcode.ISUB, 0, 4, 5,      # R0 = R4 - R5
            ]),
            name="range_sum",
            description="A itaḥ B paryantayogaḥ → sum(A..B) via Gauss formula",
            sanskrit_name="... इतः ... पर्यन्तयोगः → सम ( Gauss )",
            required_operands=2,
            operand_types=["register", "register"],
        ))

    # ===================================================================
    # Level 2: Taddhita — Secondary Derivation
    # Domain-specific vocabularies built from secondary suffixes
    # ===================================================================

    def _build_level_2(self) -> None:
        """Build Level 2 vocabulary: domain-specific derived forms.

        Taddhita words use secondary suffixes to create domain vocabularies.
        These map to specialized multi-step bytecode sequences.
        """
        # Mathematical: vargaḥ (square) → IMUL R, R, R
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+vargaḥ",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda rd=0, ra=0: bytearray([
                Opcode.IMUL, rd, ra, ra
            ]),
            name="square",
            description="A vargaḥ → IMUL (square / वर्गः)",
            sanskrit_name="... वर्गः → वर्ग (वर्गकरणम्)",
            required_operands=2,
            operand_types=["register", "register"],
        ))

        # Mathematical: mūlaḥ (square root) → iterative approximation
        self._tiles.append(VocabTile(
            pattern=r"(?P<a>\S+)\s+mūlaḥ",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda rd=0, ra=0: bytearray([
                # Simplified: Newton's method stub (would need loop)
                Opcode.MOV, rd, ra,
            ]),
            name="sqrt",
            description="A mūlaḥ → sqrt(A) (square root / मूलम्)",
            sanskrit_name="... मूलः → मूलम् (वर्गमूलम्)",
            required_operands=2,
            operand_types=["register", "register"],
        ))

        # A2A: brūhi ... (tell/notify ...) → TELL
        self._tiles.append(VocabTile(
            pattern=r"brūhi\s+(?P<r>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda r=0: bytearray([Opcode.TELL, r]),
            name="tell_agent",
            description="brūhi Rn → TELL (agent notification / सन्देशः)",
            sanskrit_name="बृहि ... → सन्देशः (अजेन्त-सूचना)",
            required_operands=1,
            operand_types=["register"],
        ))

        # A2A: pṛccha ... (ask ...) → ASK
        self._tiles.append(VocabTile(
            pattern=r"pṛccha\s+(?P<r>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda r=0: bytearray([Opcode.ASK, r]),
            name="ask_agent",
            description="pṛccha Rn → ASK (agent query / प्रश्नः)",
            sanskrit_name="पृच्छ ... → प्रश्नः",
            required_operands=1,
            operand_types=["register"],
        ))

        # A2A: niyujya ... (delegate to ...) → DELEGATE
        self._tiles.append(VocabTile(
            pattern=r"niyujya\s+(?P<r>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda r=0: bytearray([Opcode.DELEGATE, r]),
            name="delegate_task",
            description="niyujya Rn → DELEGATE (task delegation / कार्यस्थानान्तरम्)",
            sanskrit_name="नियुज्य ... → कार्यस्थानान्तरम्",
            required_operands=1,
            operand_types=["register"],
        ))

        # A2A: sarveṣāṃ kathaya (tell everyone) → BROADCAST
        self._tiles.append(VocabTile(
            pattern=r"sarveṣāṃ\s+kathaya\s+(?P<r>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda r=0: bytearray([Opcode.BROADCAST, r]),
            name="broadcast",
            description="sarveṣāṃ kathaya Rn → BROADCAST (announce to all)",
            sanskrit_name="सर्वेषां कथय ... → प्रसारः",
            required_operands=1,
            operand_types=["register"],
        ))

        # A2A: viśvāsaṃ pṛccha (check trust) → TRUST_CHECK
        self._tiles.append(VocabTile(
            pattern=r"viśvāsaṃ\s+pṛccha\s+(?P<r>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda r=0: bytearray([Opcode.TRUST_CHECK, r]),
            name="trust_check",
            description="viśvāsaṃ pṛccha Rn → TRUST_CHECK (verify trust / विश्वासपरीक्षा)",
            sanskrit_name="विश्वासं पृच्छ ... → विश्वासपरीक्षा",
            required_operands=1,
            operand_types=["register"],
        ))

        # A2A: adhikāraṃ yāca (request capability) → CAP_REQUIRE
        self._tiles.append(VocabTile(
            pattern=r"adhikāraṃ\s+yāca\s+(?P<r>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda r=0: bytearray([Opcode.CAP_REQUIRE, r]),
            name="capability_request",
            description="adhikāraṃ yāca Rn → CAP_REQUIRE (request capability / अधिकारयाचना)",
            sanskrit_name="अधिकारं याच ... → अधिकारयाचना",
            required_operands=1,
            operand_types=["register"],
        ))

        # Conditional: yady ... (if ...) → JZ
        self._tiles.append(VocabTile(
            pattern=r"yady\s+(?P<r>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda r=0, addr=0: bytearray([
                Opcode.JZ, r, addr & 0xFF, (addr >> 8) & 0xFF
            ]),
            name="if_branch",
            description="yady Rn → JZ Rn (conditional branch / यदि-शाखा)",
            sanskrit_name="यदि ... → यदि-शाखा",
            required_operands=2,
            operand_types=["register", "address"],
        ))

        # Conditional: anyathā (else) → JNZ
        self._tiles.append(VocabTile(
            pattern=r"anyathā",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda addr=0: bytearray([
                Opcode.JNZ, 0, addr & 0xFF, (addr >> 8) & 0xFF
            ]),
            name="else_branch",
            description="anyathā → JNZ (else branch / अन्यथा-शाखा)",
            sanskrit_name="अन्यथा → अन्यथा-शाखा",
            required_operands=1,
            operand_types=["address"],
        ))

        # Loop: āvṛttaḥ (repeat) → JMP back
        self._tiles.append(VocabTile(
            pattern=r"āvṛttaḥ\s+(?P<addr>\S+)",
            level=VocabLevel.TADDHITA,
            bytecode_fn=lambda addr=0: bytearray([
                Opcode.JMP, addr & 0xFF, (addr >> 8) & 0xFF
            ]),
            name="loop_back",
            description="āvṛttaḥ addr → JMP addr (loop / आवृत्तिः)",
            sanskrit_name="आवृत्तः ... → आवृत्तिः (पुनरावृत्तिः)",
            required_operands=1,
            operand_types=["address"],
        ))

    # ===================================================================
    # Level 3: Samāsa — Compound Tiles
    # Multi-step computation patterns from compound words
    # ===================================================================

    def _build_level_3(self) -> None:
        """Build Level 3 vocabulary: compound computation tiles.

        Samāsa compounds map to multi-step bytecode sequences that
        perform complete computations.  These are the highest-level
        abstractions — a single Sanskrit compound can encode an
        entire algorithm.
        """
        # rāśiyogaḥ (sum of quantities) → IADD
        self._tiles.append(VocabTile(
            pattern=r"rāśiyogaḥ",
            level=VocabLevel.SAMASA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IADD, rd, ra, rb
            ]),
            name="sum",
            description="rāśiyogaḥ — sum of quantities (राशियोगः / योगः)",
            sanskrit_name="राशियोगः → योगः",
            required_operands=3,
            operand_types=["register", "register", "register"],
        ))

        # guṇayogaḥ (product) → IMUL
        self._tiles.append(VocabTile(
            pattern=r"guṇayogaḥ",
            level=VocabLevel.SAMASA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IMUL, rd, ra, rb
            ]),
            name="product",
            description="guṇayogaḥ — product of quantities (गुणयोगः / गुणनम्)",
            sanskrit_name="गुणयोगः → गुणनम्",
            required_operands=3,
            operand_types=["register", "register", "register"],
        ))

        # bhāgahāraḥ (division) → IDIV
        self._tiles.append(VocabTile(
            pattern=r"bhāgahāraḥ",
            level=VocabLevel.SAMASA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IDIV, rd, ra, rb
            ]),
            name="quotient",
            description="bhāgahāraḥ — quotient (भागहारः / भाजनम्)",
            sanskrit_name="भागहारः → भाजनम्",
            required_operands=3,
            operand_types=["register", "register", "register"],
        ))

        # Compute-and-store tile: ... guṇayogaḥ sthira ... → IMUL then STORE
        self._tiles.append(VocabTile(
            pattern=r"guṇayogaḥ\s+sthira",
            level=VocabLevel.SAMASA,
            bytecode_fn=lambda rd=0, ra=0, rb=0: bytearray([
                Opcode.IMUL, rd, ra, rb,
                Opcode.STORE, rd, ra,  # Store result back
            ]),
            name="multiply_and_store",
            description="guṇayogaḥ sthira — multiply then store",
            sanskrit_name="गुणयोगः स्थिर → गुणनं स्थापय",
            required_operands=3,
            operand_types=["register", "register", "register"],
        ))

        # Load-compute-print tile: load ... saha ... gaṇaya ... pluta ... darśaya
        self._tiles.append(VocabTile(
            pattern=r"load\s+(?P<r1>\S+)\s+saha\s+(?P<v1>\d+)\s+.*load\s+(?P<r2>\S+)\s+saha\s+(?P<v2>\d+)\s+.*gaṇaya\s+(?P<ra>\S+)\s+pluta\s+(?P<rb>\S+)\s+.*darśaya",
            level=VocabLevel.SAMASA,
            bytecode_fn=lambda r1=1, v1=0, r2=2, v2=0, ra=0, rb=0: bytearray([
                Opcode.MOVI, r1, v1 & 0xFF, (v1 >> 8) & 0xFF,
                Opcode.MOVI, r2, v2 & 0xFF, (v2 >> 8) & 0xFF,
                Opcode.IADD, 0, ra, rb,
                Opcode.PRINT, 0,
            ]),
            name="full_compute",
            description="Complete load-compute-print sequence",
            sanskrit_name="स्थापय-गणय-दर्शय → पूर्णगणना",
            required_operands=6,
            operand_types=["register", "immediate", "register", "immediate",
                           "register", "register"],
        ))

        # Fibonacci-style iterative tile: āvṛttaḥ ... kramaśaḥ
        self._tiles.append(VocabTile(
            pattern=r"kramaśaḥ\s+āvṛttaḥ",
            level=VocabLevel.SAMASA,
            bytecode_fn=lambda: bytearray([
                # Iterative loop stub
                Opcode.PUSH, 1,
                Opcode.PUSH, 2,
                Opcode.POP, 3,
                Opcode.IADD, 1, 1, 3,
                Opcode.POP, 2,
            ]),
            name="iterative_step",
            description="kramaśaḥ āvṛttaḥ — one iteration of sequential loop",
            sanskrit_name="क्रमशः आवृत्तः → पुनरावृत्तेः एकः पदः",
            required_operands=0,
        ))

    # ---- Public API ----

    def find(self, text: str) -> list[VocabTile]:
        """Find all vocabulary tiles matching the given text.

        Tries to match from highest level (samāsa) to lowest (dhātu),
        returning the most specific matches first.

        Args:
            text: Sanskrit text (IAST or mixed) to match against.

        Returns:
            List of matching VocabTiles, ordered by level (highest first).
        """
        matches: list[VocabTile] = []

        for tile in self._tiles:
            if tile.matches(text):
                matches.append(tile)

        # Sort by level (highest first) for specificity
        matches.sort(key=lambda t: -t.level)
        return matches

    def get_tile(self, name: str) -> VocabTile | None:
        """Look up a tile by name.

        Args:
            name: The tile's registered name.

        Returns:
            The VocabTile if found, or None.
        """
        for tile in self._tiles:
            if tile.name == name:
                return tile
        return None

    def by_level(self, level: VocabLevel) -> list[VocabTile]:
        """Return all tiles at a given vocabulary level.

        Args:
            level: The VocabLevel to filter by.

        Returns:
            List of VocabTiles at the specified level.
        """
        return [t for t in self._tiles if t.level == level]

    @property
    def all_tiles(self) -> list[VocabTile]:
        """Return all registered tiles."""
        return list(self._tiles)

    @property
    def tile_count(self) -> int:
        """Return the total number of registered tiles."""
        return len(self._tiles)

    def compile_text(self, text: str, operands: list[int] | None = None) -> bytearray:
        """Compile a Sanskrit text string into bytecode using vocabulary matching.

        Tries to find the best matching tile and generates bytecode.

        Args:
            text: Sanskrit text to compile.
            operands: Operand values (registers, immediates, addresses).

        Returns:
            Generated bytecode.  Returns [NOP] if no tile matches.
        """
        matches = self.find(text)
        if not matches:
            return bytearray([Opcode.NOP])

        # Use the most specific (highest-level) match
        tile = matches[0]
        ops = operands or []
        return tile.compile(*ops)

    def level_summary(self) -> str:
        """Return a formatted summary of vocabulary by level."""
        lines = [
            "╔═══════════════════════════════════════════════════════════════╗",
            "║  Vocabulary Tiling System — FLUX-san                        ║",
            "║  शब्दावली-टाइलिङ्ग-व्यवस्था — प्रवाहिनी                      ║",
            "╠═══════════════════════════════════════════════════════════════╣",
        ]
        level_names = {
            VocabLevel.DHATU_PRAYOGA: "L0: Dhātu-prayoga (धातुप्रयोगः) — Root Application",
            VocabLevel.KRDANTA:       "L1: Kṛdanta (कृदन्तम्) — Primary Derivation",
            VocabLevel.TADDHITA:      "L2: Taddhita (तद्धितम्) — Secondary Derivation",
            VocabLevel.SAMASA:        "L3: Samāsa (समासः) — Compound Tiles",
        }

        for level in VocabLevel:
            tiles = self.by_level(level)
            count = len(tiles)
            name = level_names.get(level, f"L{level}: Unknown")
            lines.append(f"║  {name:<58s} ║")
            lines.append(f"║    Tiles: {count:<50d} ║")
            for tile in tiles:
                desc = tile.description[:52] if tile.description else tile.pattern[:52]
                lines.append(f"║      • {desc:<52s} ║")
            lines.append("║                                                           ║")

        lines.append("╚═══════════════════════════════════════════════════════════════╝")
        return "\n".join(lines)
