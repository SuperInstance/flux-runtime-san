"""
Dhātu — Verbal Root System as Opcode Generator
================================================

Sanskrit's dhātu (verbal root) system maps naturally to bytecode instruction
generation.  Every Sanskrit verb derives from one of approximately 1,947
roots (dhātūni) catalogued by Pāṇini in the Dhātupāṭha.  Each root can be
conjugated through 10 gaṇa (verb classes) and two padas (voices), producing
different instruction variants.

Root → Opcode Mapping:
  ┌───────────────────┬────────────────┬──────────────────────────────────────┐
  │ Dhātu (root)      │ IAST           │ Primary opcode(s)                    │
  ├───────────────────┼────────────────┼──────────────────────────────────────┤
  │ √bhū (to be)      │ bhū / as       │ MOV, NOP                             │
  │ √kṛ (to do/make)  │ kṛ / kar       │ CALL, MOVI, IADD                     │
  │ √dā (to give)     │ dā / dad        │ STORE, TELL                          │
  │ √adhi-īś (to rule)│ adhi-īś        │ TRUST_CHECK, CAP_REQUIRE             │
  │ √vid (to know)    │ vid / veda      │ LOAD, CMP                            │
  │ √buddh (to know)  │ buddh / bodh    │ DECODE (meta-instruction)            │
  │ √gam (to go)      │ gam / gaccha    │ JMP, CALL                            │
  │ √yuj (to join)    │ yuj / yunakti   │ IADD, ICONCAT                        │
  │ √hṛ (to take)     │ hṛ / hara       │ LOAD, POP                            │
  │ √sthā (to stand)  │ sthā / tiṣṭhati │ HALT                                │
  │ √mṛj (to rub)     │ mṛj / mṛjati   │ IMUL (rubbing = multiplying)         │
  │ √śodh (to purify) │ śodh / śodhay   │ IDIV (purification = division)       │
  │ √kṣip (to throw)  │ kṣip / kṣipati │ PUSH                                 │
  │ √pā (to drink)    │ pā / pibati     │ POP (drink/consume from stack)       │
  │ √pṛcch (to ask)   │ pṛcch / pṛcchati│ ASK                                 │
  │ √brū (to speak)   │ brū / bravīti   │ TELL, PRINT                          │
  │ √grah (to seize)  │ grah / gṛhṇāti │ LOAD, POP                            │
  │ √niyuj (to yoke)  │ niyuj / niyunakti│ DELEGATE                            │
  │ √prakṛṇ (to ask)  │ prakṛṇ         │ BROADCAST                            │
  └───────────────────┴────────────────┴──────────────────────────────────────┘

Gaṇa (Verb Classes):
  The 10 gaṇa produce instruction variants — e.g., bhvādi (class 1) uses
  the default operand order, while divādi (class 4) reverses operands,
  and curādi (class 10) appends a suffix that changes the instruction
  to a comparison or test variant.

Pada (Voice):
  - Parasmaipada (active voice): standard operand order (src, dst)
  - Ātmanepada (middle/reflexive voice): reversed or self-referential
    operand order — the result goes back into the source register.

From Pāṇini's Dhātupāṭha:
  dhātavaḥ prāṇiṇikrītāḥ — "The roots are systematized by Pāṇini"
"""

from __future__ import annotations

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any

from flux_san.vm import Opcode
from flux_san.vibhakti import Vibhakti
from flux_san.lakara import Lakara


# ---------------------------------------------------------------------------
# Gaṇa — the 10 verb classes of Sanskrit
# ---------------------------------------------------------------------------

class Gana(IntEnum):
    """Daśa-gaṇāḥ — the 10 verb classes of Sanskrit.

    Each gaṇa determines the conjugation pattern, which in our system
    maps to different bytecode instruction variants:

      1. bhvādi   → default operand order
      2. adādi    → reversed destination
      3. juhotyādi → double-register operation
      4. divādi   → reversed operand order
      5. svādi    → with immediate operand
      6. tudādi   → destructive (modifies source)
      7. rudhādi  → compound instruction (two opcodes)
      8. tanādi   → flagged operation (sets condition codes)
      9. kryādi   → returning (pushes result)
      10. curādi  → comparison/test variant
    """
    BHVADI     = 1   # भ्वादि    — default
    ADADI      = 2   # अदादि    — reversed destination
    JUHOTYADI  = 3   # जुहोत्यादि — double-register
    DIVADI     = 4   # दिवादि    — reversed operands
    SVADI      = 5   # स्वादि    — immediate operand
    TUDADI     = 6   # तुदादि    — destructive
    RUDHADI    = 7   # रुधादि   — compound
    TANADI     = 8   # तनादि    — flagged
    KRYADI     = 9   # क्र्यादि   — returning (push)
    CURADI     = 10  # चुरादि    — comparison/test


_GANA_NAMES_DEVA: dict[Gana, str] = {
    Gana.BHVADI:    "भ्वादि",
    Gana.ADADI:     "अदादि",
    Gana.JUHOTYADI: "जुहोत्यादि",
    Gana.DIVADI:    "दिवादि",
    Gana.SVADI:     "स्वादि",
    Gana.TUDADI:    "तुदादि",
    Gana.RUDHADI:   "रुधादि",
    Gana.TANADI:    "तनादि",
    Gana.KRYADI:    "क्र्यादि",
    Gana.CURADI:    "चुरादि",
}

_GANA_NAMES_IAST: dict[Gana, str] = {
    Gana.BHVADI:    "bhvādi",
    Gana.ADADI:     "adādi",
    Gana.JUHOTYADI: "juhotyādi",
    Gana.DIVADI:    "divādi",
    Gana.SVADI:     "svādi",
    Gana.TUDADI:    "tudādi",
    Gana.RUDHADI:   "rudhādi",
    Gana.TANADI:    "tanādi",
    Gana.KRYADI:    "kryādi",
    Gana.CURADI:    "curādi",
}

_GANA_DESCRIPTIONS: dict[Gana, str] = {
    Gana.BHVADI:    "default operand order",
    Gana.ADADI:     "reversed destination",
    Gana.JUHOTYADI: "double-register operation",
    Gana.DIVADI:    "reversed operand order",
    Gana.SVADI:     "with immediate operand",
    Gana.TUDADI:    "destructive (modifies source)",
    Gana.RUDHADI:   "compound instruction (two opcodes)",
    Gana.TANADI:    "flagged (sets condition codes)",
    Gana.KRYADI:    "returning (pushes result)",
    Gana.CURADI:    "comparison/test variant",
}


# ---------------------------------------------------------------------------
# Pada — voice (active / middle)
# ---------------------------------------------------------------------------

class Pada(IntEnum):
    """Dvi-pada — the two voices of Sanskrit verbs.

    Parasmaipada (active): standard operand order — R(dst) ← op(R(src1), R(src2))
    Ātmanepada (middle/reflexive): self-referential — R(src) ← op(R(src), R(other))
    """
    PARASMAIPADA = 1   # परस्मैपद — active voice
    ATMANEPADA   = 2   # आत्मनेपद  — middle/reflexive voice


_PADA_NAMES_DEVA: dict[Pada, str] = {
    Pada.PARASMAIPADA: "परस्मैपद",
    Pada.ATMANEPADA: "आत्मनेपद",
}

_PADA_NAMES_IAST: dict[Pada, str] = {
    Pada.PARASMAIPADA: "parasmaipada",
    Pada.ATMANEPADA: "ātmanepada",
}


# ---------------------------------------------------------------------------
# Dhātu — a single verbal root
# ---------------------------------------------------------------------------

@dataclass
class Dhatu:
    """A Sanskrit verbal root (dhātu) with its bytecode mapping.

    Each dhātu has:
      - root: the IAST transliteration of the root (e.g., "bhū")
      - devanagari: the root in Devanāgarī script
      - meaning: English gloss
      - primary_opcode: the main Opcode generated by this root
      - secondary_opcodes: alternative opcodes depending on gaṇa/pada
      - gana: default verb class
      - padas: supported voices
    """
    root: str                          # IAST root form (e.g., "bhū")
    devanagari: str                    # Devanāgarī form
    meaning: str                       # English gloss
    primary_opcode: Opcode             # Primary generated opcode
    secondary_opcodes: dict[Gana, Opcode] = field(default_factory=dict)
    gana: Gana = Gana.BHVADI           # Default verb class
    padas: list[Pada] = field(default_factory=lambda: [Pada.PARASMAIPADA, Pada.ATMANEPADA])
    category: str = ""                 # Semantic category

    @property
    def mnemonic(self) -> str:
        """Return the opcode mnemonic."""
        return self.primary_opcode.name

    def __repr__(self) -> str:
        return f"Dhatu(√{self.root}, {self.primary_opcode.name})"


# ---------------------------------------------------------------------------
# Dhātu registry — all known verbal roots
# ---------------------------------------------------------------------------

# Core computational roots
_DHATU_REGISTRY: dict[str, Dhatu] = {
    # --- Being / Identity ---
    "bhū": Dhatu(
        root="bhū", devanagari="भू", meaning="to be, become",
        primary_opcode=Opcode.NOP,
        secondary_opcodes={
            Gana.BHVADI: Opcode.NOP,
            Gana.SVADI: Opcode.MOVI,
            Gana.DIVADI: Opcode.MOV,
        },
        gana=Gana.BHVADI,
        category="identity",
    ),
    "as": Dhatu(
        root="as", devanagari="अस्", meaning="to be (existential)",
        primary_opcode=Opcode.NOP,
        secondary_opcodes={Gana.BHVADI: Opcode.MOV, Gana.SVADI: Opcode.MOVI},
        gana=Gana.BHVADI,
        category="identity",
    ),

    # --- Action / Execution ---
    "kṛ": Dhatu(
        root="kṛ", devanagari="कृ", meaning="to do, make, perform",
        primary_opcode=Opcode.CALL,
        secondary_opcodes={
            Gana.BHVADI: Opcode.CALL,
            Gana.SVADI: Opcode.MOVI,
            Gana.TUDADI: Opcode.IADD,
            Gana.KRYADI: Opcode.CALL,
        },
        gana=Gana.BHVADI,
        category="execution",
    ),

    # --- Giving / Storing ---
    "dā": Dhatu(
        root="dā", devanagari="दा", meaning="to give, grant, bestow",
        primary_opcode=Opcode.STORE,
        secondary_opcodes={
            Gana.BHVADI: Opcode.STORE,
            Gana.DIVADI: Opcode.TELL,
            Gana.JUHOTYADI: Opcode.DELEGATE,
        },
        gana=Gana.BHVADI,
        category="transfer",
    ),

    # --- Knowing / Loading ---
    "vid": Dhatu(
        root="vid", devanagari="विद्", meaning="to know, find, learn",
        primary_opcode=Opcode.LOAD,
        secondary_opcodes={
            Gana.BHVADI: Opcode.LOAD,
            Gana.CURADI: Opcode.CMP,
            Gana.TANADI: Opcode.ICMP,
        },
        gana=Gana.BHVADI,
        category="knowledge",
    ),

    # --- Understanding / Decoding ---
    "buddh": Dhatu(
        root="buddh", devanagari="बुध्", meaning="to wake, understand, become aware",
        primary_opcode=Opcode.CMP,
        secondary_opcodes={
            Gana.BHVADI: Opcode.CMP,
            Gana.CURADI: Opcode.ICMP,
            Gana.TANADI: Opcode.TEST,
        },
        gana=Gana.BHVADI,
        category="knowledge",
    ),

    # --- Going / Jumping ---
    "gam": Dhatu(
        root="gam", devanagari="गम्", meaning="to go, move, proceed",
        primary_opcode=Opcode.JMP,
        secondary_opcodes={
            Gana.BHVADI: Opcode.JMP,
            Gana.SVADI: Opcode.JZ,
            Gana.CURADI: Opcode.JNZ,
            Gana.KRYADI: Opcode.CALL,
        },
        gana=Gana.BHVADI,
        category="flow",
    ),

    # --- Joining / Addition ---
    "yuj": Dhatu(
        root="yuj", devanagari="युज्", meaning="to join, unite, connect",
        primary_opcode=Opcode.IADD,
        secondary_opcodes={
            Gana.BHVADI: Opcode.IADD,
            Gana.DIVADI: Opcode.ISUB,
            Gana.TUDADI: Opcode.IMUL,
            Gana.TANADI: Opcode.IADD,
        },
        gana=Gana.BHVADI,
        category="arithmetic",
    ),

    # --- Taking / Loading ---
    "hṛ": Dhatu(
        root="hṛ", devanagari="हृ", meaning="to take, carry, remove",
        primary_opcode=Opcode.POP,
        secondary_opcodes={
            Gana.BHVADI: Opcode.POP,
            Gana.DIVADI: Opcode.LOAD,
            Gana.TUDADI: Opcode.POP,
        },
        gana=Gana.BHVADI,
        category="transfer",
    ),

    # --- Standing / Halting ---
    "sthā": Dhatu(
        root="sthā", devanagari="स्था", meaning="to stand, stay, remain",
        primary_opcode=Opcode.HALT,
        secondary_opcodes={
            Gana.BHVADI: Opcode.HALT,
            Gana.SVADI: Opcode.MOVI,
            Gana.TANADI: Opcode.CMP,
        },
        gana=Gana.BHVADI,
        category="flow",
    ),

    # --- Multiplying (rubbing) ---
    "mṛj": Dhatu(
        root="mṛj", devanagari="मृज्", meaning="to rub, polish, cleanse",
        primary_opcode=Opcode.IMUL,
        secondary_opcodes={
            Gana.BHVADI: Opcode.IMUL,
            Gana.DIVADI: Opcode.IDIV,
        },
        gana=Gana.TUDADI,
        category="arithmetic",
    ),

    # --- Dividing (purifying) ---
    "śodh": Dhatu(
        root="śodh", devanagari="शोध्", meaning="to purify, cleanse",
        primary_opcode=Opcode.IDIV,
        secondary_opcodes={
            Gana.BHVADI: Opcode.IDIV,
            Gana.TUDADI: Opcode.IMOD,
        },
        gana=Gana.TUDADI,
        category="arithmetic",
    ),

    # --- Throwing / Push ---
    "kṣip": Dhatu(
        root="kṣip", devanagari="क्षिप्", meaning="to throw, cast, send",
        primary_opcode=Opcode.PUSH,
        secondary_opcodes={
            Gana.BHVADI: Opcode.PUSH,
            Gana.DIVADI: Opcode.STORE,
        },
        gana=Gana.TUDADI,
        category="stack",
    ),

    # --- Drinking / Pop ---
    "pā": Dhatu(
        root="pā", devanagari="पा", meaning="to drink, consume",
        primary_opcode=Opcode.POP,
        secondary_opcodes={
            Gana.BHVADI: Opcode.POP,
            Gana.DIVADI: Opcode.LOAD,
        },
        gana=Gana.SVADI,
        category="stack",
    ),

    # --- Asking ---
    "pṛcch": Dhatu(
        root="pṛcch", devanagari="पृच्छ्", meaning="to ask, inquire",
        primary_opcode=Opcode.ASK,
        secondary_opcodes={
            Gana.BHVADI: Opcode.ASK,
            Gana.DIVADI: Opcode.ASK,
        },
        gana=Gana.TUDADI,
        category="a2a",
    ),

    # --- Speaking / Telling ---
    "brū": Dhatu(
        root="brū", devanagari="ब्रू", meaning="to speak, say, tell",
        primary_opcode=Opcode.TELL,
        secondary_opcodes={
            Gana.BHVADI: Opcode.TELL,
            Gana.DIVADI: Opcode.PRINT,
            Gana.SVADI: Opcode.PRINT,
        },
        gana=Gana.BHVADI,
        category="a2a",
    ),

    # --- Seizing / Grasping ---
    "grah": Dhatu(
        root="grah", devanagari="ग्रह्", meaning="to seize, grasp, take",
        primary_opcode=Opcode.LOAD,
        secondary_opcodes={
            Gana.BHVADI: Opcode.LOAD,
            Gana.TUDADI: Opcode.POP,
        },
        gana=Gana.TUDADI,
        category="transfer",
    ),

    # --- Yoking / Delegating ---
    "niyuj": Dhatu(
        root="niyuj", devanagari="नियुज्", meaning="to yoke, harness, assign",
        primary_opcode=Opcode.DELEGATE,
        secondary_opcodes={
            Gana.BHVADI: Opcode.DELEGATE,
            Gana.KRYADI: Opcode.CALL,
        },
        gana=Gana.BHVADI,
        category="a2a",
    ),

    # --- Ruling / Trust ---
    "adhiīś": Dhatu(
        root="adhi-īś", devanagari="अधीश्", meaning="to rule over, master, command",
        primary_opcode=Opcode.TRUST_CHECK,
        secondary_opcodes={
            Gana.BHVADI: Opcode.TRUST_CHECK,
            Gana.CURADI: Opcode.CAP_REQUIRE,
            Gana.TANADI: Opcode.CAP_REQUIRE,
        },
        gana=Gana.BHVADI,
        category="a2a",
    ),

    # --- Proclaiming / Broadcasting ---
    "prakṛṇ": Dhatu(
        root="prakṛṇ", devanagari="प्रकृण्", meaning="to ask about, investigate publicly",
        primary_opcode=Opcode.BROADCAST,
        secondary_opcodes={Gana.BHVADI: Opcode.BROADCAST},
        gana=Gana.CURADI,
        category="a2a",
    ),

    # --- Subtracting ---
    "śoṣ": Dhatu(
        root="śoṣ", devanagari="शोष्", meaning="to consume, diminish, dry up",
        primary_opcode=Opcode.ISUB,
        secondary_opcodes={Gana.BHVADI: Opcode.ISUB, Gana.TUDADI: Opcode.DEC},
        gana=Gana.TUDADI,
        category="arithmetic",
    ),

    # --- Negating ---
    "virah": Dhatu(
        root="virah", devanagari="विरह्", meaning="to be separated from, negate",
        primary_opcode=Opcode.INEG,
        secondary_opcodes={Gana.BHVADI: Opcode.INEG, Gana.TUDADI: Opcode.DEC},
        gana=Gana.TUDADI,
        category="arithmetic",
    ),

    # --- Returning ---
    "nivṛt": Dhatu(
        root="nivṛt", devanagari="निवृत्", meaning="to turn back, return",
        primary_opcode=Opcode.RET,
        secondary_opcodes={Gana.BHVADI: Opcode.RET},
        gana=Gana.BHVADI,
        category="flow",
    ),

    # --- Comparing (equal) ---
    "samañj": Dhatu(
        root="samañj", devanagari="समञ्ज्", meaning="to equate, balance",
        primary_opcode=Opcode.CMP,
        secondary_opcodes={
            Gana.BHVADI: Opcode.CMP,
            Gana.CURADI: Opcode.ICMP,
            Gana.TANADI: Opcode.IEQ,
        },
        gana=Gana.CURADI,
        category="comparison",
    ),
}


# ---------------------------------------------------------------------------
# Conjugation — generating bytecode from a dhātu + gaṇa + pada
# ---------------------------------------------------------------------------

@dataclass
class Conjugation:
    """A conjugated verbal form that produces bytecode.

    The conjugation captures the full grammatical context:
      - dhātu: the verbal root
      - gana: the verb class (determines instruction variant)
      - pada: the voice (determines operand order)
      - lakara: the tense/mood (determines execution mode prefix)
      - operands: register/immediate arguments
    """
    dhatu: Dhatu
    gana: Gana = Gana.BHVADI
    pada: Pada = Pada.PARASMAIPADA
    lakara: Lakara = Lakara.LAT
    operands: list[int] = field(default_factory=list)

    @property
    def opcode(self) -> Opcode:
        """Resolve the effective opcode from dhātu + gaṇa."""
        if self.gana in self.dhatu.secondary_opcodes:
            return self.dhatu.secondary_opcodes[self.gana]
        return self.dhatu.primary_opcode

    @property
    def is_reflexive(self) -> bool:
        """True if ātmanepada (middle voice) — result goes back to source."""
        return self.pada == Pada.ATMANEPADA

    def bytecode(self) -> bytearray:
        """Generate the bytecode for this conjugation.

        Operand layout depends on the opcode family:
          - 3-register (IADD, ISUB, IMUL, IDIV, IMOD):
            Parasmaipada: [OP, dst, src1, src2]
            Ātmanepada:   [OP, src1, src1, src2] (result overwrites src1)
          - 2-register (MOV, LOAD, STORE):
            Parasmaipada: [OP, dst, src]
            Ātmanepada:   [OP, src, src]
          - 1-register (PUSH, POP, INC, DEC, INEG, PRINT):
            [OP, reg]
          - 0-operand (HALT, NOP, RET):
            [OP]
          - Immediate (MOVI):
            [OP, reg, lo, hi]
          - Branch (JMP, JE, JNE):
            [OP, addr_lo, addr_hi]
          - Conditional branch (JZ, JNZ):
            [OP, reg, addr_lo, addr_hi]
        """
        op = self.opcode
        ops = list(self.operands)
        bc = bytearray()

        # 3-register instructions
        if op in (Opcode.IADD, Opcode.ISUB, Opcode.IMUL, Opcode.IDIV, Opcode.IMOD,
                   Opcode.IAND, Opcode.IOR, Opcode.IXOR,
                   Opcode.IEQ, Opcode.ILT, Opcode.ILE, Opcode.IGT, Opcode.IGE):
            if self.is_reflexive and len(ops) >= 2:
                # Ātmanepada: dst = src1 (result overwrites first operand)
                bc.extend([op, ops[0], ops[0], ops[1]])
            elif len(ops) >= 3:
                bc.extend([op, ops[0], ops[1], ops[2]])
            elif len(ops) == 2:
                bc.extend([op, 0, ops[0], ops[1]])  # Default dst = R0
            elif len(ops) == 1:
                bc.extend([op, ops[0], ops[0], 0])  # dst = src1, src2 = 0

        # 2-register instructions
        elif op in (Opcode.MOV, Opcode.LOAD, Opcode.STORE, Opcode.CALL_IND):
            if self.is_reflexive and len(ops) >= 1:
                bc.extend([op, ops[0], ops[0]])
            elif len(ops) >= 2:
                bc.extend([op, ops[0], ops[1]])
            elif len(ops) == 1:
                bc.extend([op, 0, ops[0]])

        # Compare instructions
        elif op in (Opcode.ICMP, Opcode.CMP):
            if len(ops) >= 2:
                bc.extend([op, ops[0], ops[1]])
            elif len(ops) == 1:
                bc.extend([op, ops[0], 0])

        # 1-register instructions
        elif op in (Opcode.PUSH, Opcode.POP, Opcode.INC, Opcode.DEC,
                     Opcode.INEG, Opcode.INOT, Opcode.TEST,
                     Opcode.PRINT, Opcode.TELL, Opcode.ASK,
                     Opcode.DELEGATE, Opcode.BROADCAST,
                     Opcode.TRUST_CHECK, Opcode.CAP_REQUIRE):
            if len(ops) >= 1:
                bc.extend([op, ops[0]])
            else:
                bc.extend([op, 0])

        # 0-operand instructions
        elif op in (Opcode.NOP, Opcode.HALT, Opcode.RET,
                     Opcode.DUP, Opcode.SWAP, Opcode.ROT):
            bc.extend([op])

        # Immediate instructions (MOVI)
        elif op == Opcode.MOVI:
            if len(ops) >= 2:
                reg, imm = ops[0], ops[1]
                imm_u = imm & 0xFFFF
                bc.extend([op, reg, imm_u & 0xFF, (imm_u >> 8) & 0xFF])
            elif len(ops) == 1:
                bc.extend([op, ops[0], 0, 0])

        # Unconditional branch
        elif op in (Opcode.JMP, Opcode.JE, Opcode.JNE, Opcode.CALL):
            if len(ops) >= 1:
                addr = ops[0] & 0xFFFF
                bc.extend([op, addr & 0xFF, (addr >> 8) & 0xFF])
            else:
                bc.extend([op, 0, 0])

        # Conditional branch (register + address)
        elif op in (Opcode.JZ, Opcode.JNZ):
            if len(ops) >= 2:
                reg, addr = ops[0], ops[1] & 0xFFFF
                bc.extend([op, reg, addr & 0xFF, (addr >> 8) & 0xFF])
            elif len(ops) == 1:
                bc.extend([op, ops[0], 0, 0])
            else:
                bc.extend([op, 0, 0, 0])

        else:
            # Fallback — emit opcode only
            bc.extend([op])

        return bc

    def describe(self) -> str:
        """Return a human-readable description of this conjugation."""
        voice = "ātmanepada" if self.is_reflexive else "parasmaipada"
        return (
            f"√{self.dhatu.root} [{self.dhatu.meaning}] "
            f"→ {self.opcode.name} "
            f"(gaṇa={self.gana.iast}, pada={voice}, "
            f"lakāra={self.lakara.iast}, ops={self.operands})"
        )


# ---------------------------------------------------------------------------
# Dhātu compiler — high-level interface
# ---------------------------------------------------------------------------

class DhatuCompiler:
    """Compiles Sanskrit verbal forms into FLUX bytecode.

    The DhatuCompiler resolves a conjugated verb to a Conjugation object,
    then emits bytecode.  It supports:
      - Direct root lookup (e.g., "bhū", "kṛ", "gam")
      - Inflected form lookup (e.g., "bhavati", "gacchati", "karoti")
      - Gaṇa-qualified lookup (e.g., "bhū:4" for divādi class)
      - Pada-qualified lookup (e.g., "kṛ@atmane" for ātmanepada)

    Usage::

        compiler = DhatuCompiler()

        # Simple root → bytecode
        bc = compiler.compile("bhū")          # NOP
        bc = compiler.compile("gam", [0x20])  # JMP 0x20

        # With operands
        bc = compiler.compile("yuj", [0, 1, 2])  # IADD R0, R1, R2

        # With gaṇa variant
        bc = compiler.compile("gam:5", [1, 0x30])  # JZ R1, 0x30

        # With pada
        bc = compiler.compile("yuj@atmane", [1, 2])  # IADD R1, R1, R2
    """

    def __init__(self):
        self._registry = dict(_DHATU_REGISTRY)
        # Build inflected-form index
        self._inflected: dict[str, tuple[str, Gana, Pada]] = {}
        self._build_inflected_index()

    def _build_inflected_index(self) -> None:
        """Build an index of common inflected forms → root mappings.

        Maps 3rd person singular present indicative (laṭ / parasmaipada)
        forms to their roots for quick lookup.
        """
        # Common present-tense forms (laṭ, 3sg parasmaipada)
        _PRESENT_FORMS: dict[str, tuple[str, Gana, Pada]] = {
            # bhvādi class 1
            "bhavati":  ("bhū", Gana.BHVADI, Pada.PARASMAIPADA),
            "karoti":   ("kṛ",  Gana.BHVADI, Pada.PARASMAIPADA),
            "dadāti":   ("dā",  Gana.BHVADI, Pada.PARASMAIPADA),
            "veda":     ("vid", Gana.BHVADI, Pada.PARASMAIPADA),
            "bodhati":  ("buddh", Gana.BHVADI, Pada.PARASMAIPADA),
            "gacchati": ("gam", Gana.BHVADI, Pada.PARASMAIPADA),
            "yunakti":  ("yuj", Gana.BHVADI, Pada.PARASMAIPADA),
            "harati":   ("hṛ",  Gana.BHVADI, Pada.PARASMAIPADA),
            "tiṣṭhati": ("sthā", Gana.BHVADI, Pada.PARASMAIPADA),
            "bravīti":  ("brū", Gana.BHVADI, Pada.PARASMAIPADA),
            "gṛhṇāti": ("grah", Gana.BHVADI, Pada.PARASMAIPADA),
            "kṣipati":  ("kṣip", Gana.BHVADI, Pada.PARASMAIPADA),
            "pibati":   ("pā",  Gana.BHVADI, Pada.PARASMAIPADA),
            "pṛcchati": ("pṛcch", Gana.BHVADI, Pada.PARASMAIPADA),
            "mṛjati":   ("mṛj", Gana.BHVADI, Pada.PARASMAIPADA),
            "śodhayati": ("śodh", Gana.BHVADI, Pada.PARASMAIPADA),
            "śoṣayati": ("śoṣ", Gana.BHVADI, Pada.PARASMAIPADA),
            "niyunakti": ("niyuj", Gana.BHVADI, Pada.PARASMAIPADA),
            "adhiśate": ("adhiīś", Gana.BHVADI, Pada.PARASMAIPADA),
            "nivartate": ("nivṛt", Gana.BHVADI, Pada.PARASMAIPADA),

            # Ātmanepada forms (class 1)
            "bhavate":  ("bhū", Gana.BHVADI, Pada.ATMANEPADA),
            "karote":   ("kṛ",  Gana.BHVADI, Pada.ATMANEPADA),
            "dadate":   ("dā",  Gana.BHVADI, Pada.ATMANEPADA),
            "yunkte":   ("yuj", Gana.BHVADI, Pada.ATMANEPADA),
            "gacchate": ("gam", Gana.BHVADI, Pada.ATMANEPADA),
            "tiṣṭhate": ("sthā", Gana.BHVADI, Pada.ATMANEPADA),
        }
        self._inflected.update(_PRESENT_FORMS)

    def lookup(self, form: str) -> Dhatu | None:
        """Look up a dhātu by root or inflected form.

        Supports:
          - Root form: "bhū", "kṛ", "gam"
          - Inflected form: "bhavati", "karoti", "gacchati"
        """
        # Direct root lookup
        if form in self._registry:
            return self._registry[form]

        # Inflected form lookup
        if form in self._inflected:
            root_key, _, _ = self._inflected[form]
            return self._registry.get(root_key)

        # Strip prefixes (upasarga) and try again
        _PREFIXES = ["pra", "parā", "ni", "niḥ", "sam", "anu", "upa",
                      "apa", "ava", "vi", "dur", "su", "ati", "adhi",
                      "pari", "anu", "abhi", "uti", "ā"]
        for prefix in _PREFIXES:
            if form.startswith(prefix) and len(form) > len(prefix) + 1:
                stem = form[len(prefix):]
                if stem in self._registry:
                    return self._registry[stem]
                if stem in self._inflected:
                    root_key, _, _ = self._inflected[stem]
                    return self._registry.get(root_key)

        return None

    def resolve_form(
        self, form: str
    ) -> tuple[Dhatu, Gana, Pada] | None:
        """Resolve a possibly-qualified form string.

        Formats:
          - "root"             → (dhatu, BHVADI, PARASMAIPADA)
          - "root:gaṇa_num"   → (dhatu, gaṇa, PARASMAIPADA)
          - "root@pada_name"  → (dhatu, BHVADI, pada)
          - "root:gaṇa@pada"  → (dhatu, gaṇa, pada)

        Examples:
          - "yuj"             → √yuj, bhvādi, parasmaipada → IADD
          - "yuj:4"           → √yuj, divādi, parasmaipada → ISUB
          - "yuj@atmane"      → √yuj, bhvādi, ātmanepada → IADD (reflexive)
          - "gam:5"           → √gam, svādi, parasmaipada → JZ
        """
        gana = Gana.BHVADI
        pada = Pada.PARASMAIPADA
        root_form = form

        # Parse qualifiers
        if "@" in root_form:
            parts = root_form.split("@", 1)
            root_form = parts[0]
            pada_name = parts[1].strip().lower()
            if "atmane" in pada_name or "ātmane" in pada_name:
                pada = Pada.ATMANEPADA

        if ":" in root_form:
            parts = root_form.split(":", 1)
            root_form = parts[0].strip()
            try:
                gana = Gana(int(parts[1].strip()))
            except ValueError:
                pass

        # Look up the dhātu
        dhatu = self.lookup(root_form)
        if dhatu is None:
            return None

        return (dhatu, gana, pada)

    def conjugate(
        self,
        root: str,
        operands: list[int] | None = None,
        gana: Gana = Gana.BHVADI,
        pada: Pada = Pada.PARASMAIPADA,
        lakara: Lakara = Lakara.LAT,
    ) -> Conjugation | None:
        """Create a Conjugation from a root with grammatical parameters.

        Args:
            root: The dhātu root or inflected form (IAST).
            operands: Register/immediate arguments.
            gana: Verb class (defaults to bhvādi).
            pada: Voice (defaults to parasmaipada).
            lakara: Tense/mood (defaults to laṭ / present).

        Returns:
            A Conjugation object, or None if the root is unknown.
        """
        dhatu = self.lookup(root)
        if dhatu is None:
            return None
        return Conjugation(
            dhatu=dhatu,
            gana=gana,
            pada=pada,
            lakara=lakara,
            operands=operands or [],
        )

    def compile(
        self,
        form: str,
        operands: list[int] | None = None,
        lakara: Lakara = Lakara.LAT,
    ) -> bytearray:
        """Compile a qualified form string directly to bytecode.

        Args:
            form: Root with optional gaṇa/pada qualifiers.
                E.g., "yuj", "yuj:4", "yuj@atmane", "gam:5@atmane"
            operands: Register/immediate arguments.
            lakara: Tense/mood for execution mode.

        Returns:
            Bytecode as bytearray.  Returns [NOP] if form is unrecognized.
        """
        resolved = self.resolve_form(form)
        if resolved is None:
            return bytearray([Opcode.NOP])

        dhatu, gana, pada = resolved
        conj = Conjugation(
            dhatu=dhatu,
            gana=gana,
            pada=pada,
            lakara=lakara,
            operands=operands or [],
        )
        return conj.bytecode()

    def compile_sequence(
        self,
        forms: list[tuple[str, list[int]]],
        lakara: Lakara = Lakara.LAT,
    ) -> bytearray:
        """Compile a sequence of (form, operands) pairs into combined bytecode.

        Args:
            forms: List of (form_string, operands_list) tuples.
            lakara: Default tense/mood for all instructions.

        Returns:
            Combined bytecode as bytearray.
        """
        bc = bytearray()
        for form, ops in forms:
            bc.extend(self.compile(form, ops, lakara))
        return bc

    @property
    def known_roots(self) -> list[str]:
        """Return a sorted list of all known dhātu roots."""
        return sorted(self._registry.keys())

    @property
    def known_inflected_forms(self) -> list[str]:
        """Return a sorted list of all indexed inflected forms."""
        return sorted(self._inflected.keys())

    def root_table(self) -> str:
        """Return a formatted table of all known dhātu roots."""
        lines = [
            "╔═══════════════════════════════════════════════════════════════════╗",
            "║  Dhātupāṭha — FLUX-san Verbal Root → Opcode Mapping              ║",
            "║  धातुपाठः — क्रियामूलम् → सङ्केतम्                                ║",
            "╠════════════╦═══════════╦═══════════════════╦═══════════════════════╣",
            "║  Root      ║ Devanāgarī ║ Meaning           ║ Primary Opcode       ║",
            "╠════════════╬═══════════╬═══════════════════╬═══════════════════════╣",
        ]
        for root in sorted(self._registry.keys()):
            d = self._registry[root]
            lines.append(
                f"║  √{root:<8s} ║ {d.devanagari:<9s} ║ {d.meaning:<17s} "
                f"║ {d.primary_opcode.name:<19s} ║"
            )
        lines.append("╚════════════╩═══════════╩═══════════════════╩═══════════════════════╝")
        return "\n".join(lines)

    def gana_table(self) -> str:
        """Return a formatted table of the 10 gaṇa (verb classes)."""
        lines = [
            "╔═════════════════════════════════════════════════════════════════╗",
            "║  Daśa-gaṇāḥ — The 10 Verb Classes of Sanskrit                 ║",
            "║  दशगणाः — संस्कृतव्याकरणस्य क्रियागणाः                           ║",
            "╠════════════════╦══════════════╦═════════════════════════════════╣",
            "║  Gaṇa          ║ Sanskrit     ║ Instruction Variant            ║",
            "╠════════════════╬══════════════╬═════════════════════════════════╣",
        ]
        for g in Gana:
            lines.append(
                f"║  {g.value:>2d}. {g.iast:<10s} ║ {g.devanagari:<12s} "
                f"║ {_GANA_DESCRIPTIONS[g]:<31s} ║"
            )
        lines.append("╚════════════════╩══════════════╩═══════════════════════════════╝")
        return "\n".join(lines)
