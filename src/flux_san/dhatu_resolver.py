"""
DhatuOpcodeResolver — Extended Root → Opcode with Properties
==============================================================

50+ Sanskrit verbal roots (dhātūni)에 opcode 매핑을 확장.
각 dhātu는 고유한 속성을 가짐:
  - Transitivity (타동/자동/양태)
  - Valency (인자 수: 1, 2, 3)
  - Semantic class (의미 범주)
  - Thi (तिङ्) verb endings → instruction arity

Pāṇini's Dhātupāṭha:
  dhātavaḥ prāṇiṇikrītāḥ — "The roots are systematized by Pāṇini"
"""

from __future__ import annotations

from enum import IntEnum, auto
from dataclasses import dataclass, field
from typing import Optional

from flux_san.vm import Opcode
from flux_san.dhatu import (
    Dhatu,
    DhatuCompiler,
    Gana,
    Pada,
    Conjugation,
    _DHATU_REGISTRY,
)
from flux_san.lakara import Lakara


# ═══════════════════════════════════════════════════════════════
# Dhātu 속성
# ═══════════════════════════════════════════════════════════════

class Transitivity(IntEnum):
    """동사 타동성 — dhātu의 논항 구조."""
    INTRANSITIVE = 0   # 자동사 (no object required)
    TRANSITIVE = 1     # 타동사 (requires object)
    DITRANSITIVE = 2   # 쌍타동사 (requires indirect + direct object)
    AMBIGUOUS = 3      # 양태동사 (can be either)


class Valency(IntEnum):
    """Dhātu valency — 필요한 인자 수 (Thi verb endings → instruction arity)."""
    VALENCY_1 = 1  # 1 인자 (주어만)
    VALENCY_2 = 2  # 2 인자 (주어 + 목적어)
    VALENCY_3 = 3  # 3 인자 (주어 + 간접목적어 + 직접목적어)
    VALENCY_VAR = 0  # 가변 인자


class SemanticClass(IntEnum):
    """Dhātu 의미 범주 — opcode 계열 분류."""
    EXISTENCE = auto()     # 존재/상태 (NOP, MOV)
    ACTION = auto()        # 동작/실행 (CALL, EXEC)
    TRANSFER = auto()      # 전달/이동 (STORE, LOAD, PUSH, POP)
    KNOWLEDGE = auto()     # 지식/인식 (CMP, QUERY)
    MOTION = auto()        # 이동/흐름 (JMP, GOTO)
    ARITHMETIC = auto()    # 산술 (IADD, ISUB, IMUL, IDIV)
    CREATION = auto()      # 생성/조합 (ICONCAT, BUILD)
    COMMUNICATION = auto() # 통신/A2A (TELL, ASK, DELEGATE)
    CONTROL = auto()       # 제어 흐름 (HALT, RET, JE, JNE)
    DESTRUCTION = auto()   # 파괴/제거 (DEC, INEG, MOD)
    PERCEPTION = auto()    # 인지/감각 (TEST, ICMP)
    AUTHORITY = auto()     # 권한/통제 (CAP_REQUIRE, TRUST_CHECK)


class ThiArity(IntEnum):
    """Thi (तिङ्) verb endings → instruction arity.

    Sanskrit verb endings encode person/number/tense which maps to
    the number of operands an instruction takes.

    Person (पुरुष):
      prathama (1st) → unary instructions (1 operand)
      madhyama (2nd) → binary instructions (2 operands)
      uttama (3rd) → ternary instructions (3 operands)

    Number (वचन):
      ekavacana (singular) → 1 register
      dvivacana (dual) → 2 registers (pairwise)
      bahuvacana (plural) → N registers (variadic)
    """
    PERSON_1ST = 1    # 단수 인자 → unary op
    PERSON_2ND = 2    # 이중 인자 → binary op
    PERSON_3RD = 3    # 삼중 인자 → ternary op

    NUMBER_SINGULAR = 1
    NUMBER_DUAL = 2
    NUMBER_PLURAL = 3

    @staticmethod
    def person_to_arity(person: int) -> int:
        """Person 번호 → instruction operand count."""
        return person  # 1st=unary, 2nd=binary, 3rd=ternary


# ═══════════════════════════════════════════════════════════════
# 확장 Dhātu 등록
# ═══════════════════════════════════════════════════════════════

@dataclass
class DhatuProperty:
    """Dhātu 고유 속성.

    Attributes:
        root: IAST root form
        transitivity: 타동성
        valency: 기본 valency
        semantic_class: 의미 범주
        meaning_en: English gloss
        is_ancient: 고대 인도 철학적 용어 여부
        note: 추가 설명
    """
    root: str
    transitivity: Transitivity = Transitivity.AMBIGUOUS
    valency: Valency = Valency.VALENCY_VAR
    semantic_class: SemanticClass = SemanticClass.ACTION
    meaning_en: str = ""
    is_ancient: bool = False
    note: str = ""


# 50+ dhātu 속성 데이터베이스
_DHATU_PROPERTIES: dict[str, DhatuProperty] = {
    # ── 존재/상태 ──
    "bhū": DhatuProperty("bhū", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.EXISTENCE, "to be, become", True),
    "as": DhatuProperty("as", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                         SemanticClass.EXISTENCE, "to be (existential)", True),
    "sthā": DhatuProperty("sthā", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                           SemanticClass.CONTROL, "to stand, remain", True),
    "vṛt": DhatuProperty("vṛt", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.EXISTENCE, "to choose, prefer"),
    "vid": DhatuProperty("vid", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.KNOWLEDGE, "to know, find", True),

    # ── 동작/실행 ──
    "kṛ": DhatuProperty("kṛ", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.ACTION, "to do, make", True),
    "kar": DhatuProperty("kar", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.ACTION, "to do (variant)"),
    "cur": DhatuProperty("cur", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.ACTION, "to steal, take"),
    "tan": DhatuProperty("tan", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.CREATION, "to spread, extend"),
    "krīḍ": DhatuProperty("krīḍ", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                           SemanticClass.CREATION, "to buy, purchase"),
    "dā": DhatuProperty("dā", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                        SemanticClass.TRANSFER, "to give, grant", True),

    # ── 이동/흐름 ──
    "gam": DhatuProperty("gam", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                         SemanticClass.MOTION, "to go", True),
    "i": DhatuProperty("i", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                       SemanticClass.MOTION, "to go, move"),
    "ā-gam": DhatuProperty("ā-gam", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                            SemanticClass.MOTION, "to come"),
    "pat": DhatuProperty("pat", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                         SemanticClass.MOTION, "to fly, fall"),
    "plav": DhatuProperty("plav", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                           SemanticClass.MOTION, "to swim, float"),
    "sṛj": DhatuProperty("sṛj", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.CREATION, "to emit, create"),

    # ── 전달/이동 ──
    "hṛ": DhatuProperty("hṛ", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                        SemanticClass.TRANSFER, "to take, carry", True),
    "grah": DhatuProperty("grah", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                          SemanticClass.TRANSFER, "to seize, grasp"),
    "kṣip": DhatuProperty("kṣip", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                           SemanticClass.TRANSFER, "to throw, cast"),
    "pā": DhatuProperty("pā", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                        SemanticClass.DESTRUCTION, "to drink, consume", True),

    # ── 지식/인식 ──
    "buddh": DhatuProperty("buddh", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                           SemanticClass.KNOWLEDGE, "to understand, become aware"),
    "jñā": DhatuProperty("jñā", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.KNOWLEDGE, "to know (cognate of Greek gnosis)", True),
    "pṛcch": DhatuProperty("pṛcch", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                           SemanticClass.COMMUNICATION, "to ask, inquire"),
    "śru": DhatuProperty("śru", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                        SemanticClass.PERCEPTION, "to hear"),
    "dṛś": DhatuProperty("dṛś", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.PERCEPTION, "to see, perceive"),
    "spaś": DhatuProperty("spaś", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                          SemanticClass.PERCEPTION, "to see"),
    "smṛ": DhatuProperty("smṛ", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.KNOWLEDGE, "to remember"),
    "man": DhatuProperty("man", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                        SemanticClass.KNOWLEDGE, "to think, believe"),
    "budh": DhatuProperty("budh", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                          SemanticClass.KNOWLEDGE, "to know, awaken"),

    # ── 산술 ──
    "yuj": DhatuProperty("yuj", Transitivity.DITRANSITIVE, Valency.VALENCY_3,
                         SemanticClass.ARITHMETIC, "to join, unite, connect", True),
    "mṛj": DhatuProperty("mṛj", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.ARITHMETIC, "to rub, polish (=multiply)"),
    "śodh": DhatuProperty("śodh", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                          SemanticClass.ARITHMETIC, "to purify, cleanse (=divide)"),
    "śoṣ": DhatuProperty("śoṣ", transitivity=Transitivity.TRANSITIVE, valency=Valency.VALENCY_2,
                          SemanticClass=SemanticClass.DESTRUCTION, meaning_en="to consume, diminish"),
    "virah": DhatuProperty("virah", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                           SemanticClass.DESTRUCTION, "to be separated, negate"),

    # ── 조합/생성 ──
    "sṛj": DhatuProperty("sṛj", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.CREATION, "to create, emit"),
    "bhav": DhatuProperty("bhav", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.EXISTENCE, "to become"),
    "nip": DhatuProperty("nip", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                        SemanticClass.DESTRUCTION, "to destroy, ruin"),
    "rudh": DhatuProperty("rudh", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.CONTROL, "to obstruct, prevent"),
    "bandh": DhatuProperty("bandh", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                           SemanticClass.CONTROL, "to bind, tie"),
    "muc": DhatuProperty("muc", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.CONTROL, "to release, free"),
    "likh": DhatuProperty("likh", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                          SemanticClass.CREATION, "to write"),

    # ── 통신/A2A ──
    "brū": DhatuProperty("brū", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.COMMUNICATION, "to speak, tell", True),
    "vac": DhatuProperty("vac", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                         SemanticClass.COMMUNICATION, "to speak, say"),
    "niyuj": DhatuProperty("niyuj", Transitivity.TRANSITIVE, Valency.VALENCY_3,
                           SemanticClass.COMMUNICATION, "to yoke, assign, delegate"),
    "prakṛṇ": DhatuProperty("prakṛṇ", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                             SemanticClass.COMMUNICATION, "to investigate publicly"),
    "adhiīś": DhatuProperty("adhi-īś", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                            SemanticClass.AUTHORITY, "to rule over, master", True),
    "niyam": DhatuProperty("niyam", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                           SemanticClass.AUTHORITY, "to govern, regulate"),
    "śās": DhatuProperty("śās", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                         SemanticClass.AUTHORITY, "to instruct, command"),
    "anuśās": DhatuProperty("anuśās", Transitivity.TRANSITIVE, Valency.VALENCY_3,
                            SemanticClass.AUTHORITY, "to command, direct"),
    "ājñā": DhatuProperty("ājñā", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                          SemanticClass.AUTHORITY, "to order, command"),
    "upadiś": DhatuProperty("upadiś", Transitivity.TRANSITIVE, Valency.VALENCY_3,
                            SemanticClass.AUTHORITY, "to teach, instruct"),
    "pṛthag": DhatuProperty("pṛthag", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                            SemanticClass.ACTION, "to ask about"),

    # ── 제어 흐름 ──
    "nivṛt": DhatuProperty("nivṛt", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                           SemanticClass.CONTROL, "to turn back, return"),
    "samañj": DhatuProperty("samañj", Transitivity.TRANSITIVE, Valency.VALENCY_2,
                           SemanticClass.CONTROL, "to equate, balance"),
    "āsād": DhatuProperty("āsād", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.MOTION, "to sit, be established"),
    "svāp": DhatuProperty("svāp", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.EXISTENCE, "to sleep"),
    "jāgr": DhatuProperty("jāgr", Transitivity.INTRANSITIVE, Valency.VALENCY_1,
                          SemanticClass.EXISTENCE, "to be awake"),
}


# ═══════════════════════════════════════════════════════════════
# Dhātu Opcode Resolver
# ═══════════════════════════════════════════════════════════════

class DhatuOpcodeResolver:
    """Dhātu Opcode Resolver — 확장된 root → opcode 해석.

    기존 DhatuCompiler를 확장하여:
      1. 50+ root에 대한 속성 기반 해석
      2. Thi (तिङ्) verb endings → instruction arity 결정
      3. Transitivity에 따른 operand layout
      4. Semantic class에 따른 opcode 계열 선택

    Usage::

        resolver = DhatuOpcodeResolver()
        prop = resolver.get_property("kṛ")
        # → DhatuProperty(root="kṛ", trans=TRANSITIVE, val=2, class=ACTION)

        arity = resolver.resolve_arity("yuj", person=3, number=1)
        # → 3 (3rd person = ternary instruction)

        result = resolver.resolve_opcode("kṛ")
        # → (Opcode.CALL, Transitivity.TRANSITIVE, Valency.VALENCY_2)
    """

    def __init__(self):
        self._compiler = DhatuCompiler()
        self._properties = dict(_DHATU_PROPERTIES)

    def get_property(self, root: str) -> Optional[DhatuProperty]:
        """Dhātu 속성 조회.

        Args:
            root: IAST root form

        Returns:
            속성 객체 (없으면 None)
        """
        return self._properties.get(root)

    def resolve_opcode(self, root: str) -> tuple[Opcode, DhatuProperty] | None:
        """Root에서 opcode + 속성을 해석.

        Args:
            root: IAST root form or inflected form

        Returns:
            (Opcode, DhatuProperty) 튜플 또는 None
        """
        dhatu = self._compiler.lookup(root)
        if dhatu is None:
            return None

        prop = self._properties.get(root)
        if prop is None:
            prop = DhatuProperty(
                root=dhatu.root,
                meaning_en=dhatu.meaning,
                transitivity=Transitivity.AMBIGUOUS,
            )

        return (dhatu.primary_opcode, prop)

    def resolve_arity(
        self,
        root: str,
        person: int = ThiArity.PERSON_3RD,
        number: int = ThiArity.NUMBER_SINGULAR,
    ) -> int:
        """Thi verb endings → instruction arity.

        Person × Number → operand count:
          3rd × singular → valency of root
          3rd × dual     → valency × 2 (pairwise)
          3rd × plural   → valency × N (variadic)
          1st             → 1 (always unary)
          2nd             → min(valency, 2) (binary)

        Args:
            root: IAST root form
            person: person (1, 2, 3)
            number: number (1=singular, 2=dual, 3=plural)

        Returns:
            Instruction operand count
        """
        prop = self._properties.get(root)
        base_valency = prop.valency if prop else Valency.VALENCY_2

        if person == ThiArity.PERSON_1ST:
            return 1
        elif person == ThiArity.PERSON_2ND:
            return min(int(base_valency), 2)
        else:  # 3rd person
            if number == ThiArity.NUMBER_DUAL:
                return int(base_valency) * 2
            elif number == ThiArity.NUMBER_PLURAL:
                return int(base_valency) + 1  # base + rest
            return int(base_valency)

    def get_transitive_operands(
        self, root: str, operands: list[int] | None = None
    ) -> list[int]:
        """Transitivity에 따른 operand layout.

        Intransitive: [dst] (no source operand)
        Transitive:   [dst, src]
        Ditransitive: [dst, src1, src2]

        Args:
            root: IAST root form
            operands: 제공된 피연산자

        Returns:
            재배열된 피연산자 목록
        """
        prop = self._properties.get(root)
        if prop is None:
            return operands or []

        ops = operands or []

        match prop.transitivity:
            case Transitivity.INTRANSITIVE:
                return ops[:1] if ops else [0]
            case Transitivity.TRANSITIVE:
                return ops[:2] if len(ops) >= 2 else ops + [0] * (2 - len(ops))
            case Transitivity.DITRANSITIVE:
                return ops[:3] if len(ops) >= 3 else ops + [0] * (3 - len(ops))
            case _:
                return ops

    def lookup_by_semantic_class(self, cls: SemanticClass) -> list[str]:
        """의미 범주로 dhātu 검색.

        Args:
            cls: 의미 범주

        Returns:
            해당 범주의 dhātu root 목록
        """
        return [
            root for root, prop in self._properties.items()
            if prop.semantic_class == cls
        ]

    def lookup_ancient(self) -> list[str]:
        """고대 인도 철학 용어 dhātu 검색.

        Vedic/Upanishadic roots with special significance.
        """
        return [
            root for root, prop in self._properties.items()
            if prop.is_ancient
        ]

    def full_table(self) -> str:
        """전체 dhātu 속성 테이블."""
        lines = [
            "╔══════════╦═════════════╦════════════════╦═══════════╦═══════════════════════╗",
            "║ Root     ║ Meaning    ║ Transitivity ║ Valency ║ Semantic Class        ║",
            "╠══════════╬═════════════╬════════════════╬═══════════╬═══════════════════════╣",
        ]
        for root in sorted(self._properties.keys()):
            prop = self._properties[root]
            trans = prop.transitivity.name
            val = str(int(prop.valency)) if prop.valency != Valency.VALENCY_VAR else "var"
            ancient = " ★" if prop.is_ancient else "  "
            lines.append(
                f"║ √{root:<8s}║ {prop.meaning_en:<11s} "
                f"║ {trans:<13s}║ {val:<9s} ║ {prop.semantic_class.name:<20s}{ancient} ║"
            )
        lines.append("╚══════════╩═════════════╩════════════════╩═══════════╩═══════════════════════╝")
        return "\n".join(lines)

    @property
    def known_roots(self) -> list[str]:
        return sorted(self._properties.keys())

    @property
    def num_roots(self) -> int:
        return len(self._properties)
