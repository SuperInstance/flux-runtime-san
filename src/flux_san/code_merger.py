"""
SandhiCodeMerger — Phonological Fusion as Code Merging
======================================================

산디(Sandhi) 음운 결합 규칙을 코드 병합으로 확장.
기존 SandhiEngine의 규칙을 활용하여:

  1. External sandhi (바깥 결합): 함수 인터페이스를 자동 적응
     두 함수가 결합될 때 산디 규칙이 인터페이스 적응을 결정.
     예: func_A + func_B → merged_func (인터페이스 자동 병합)

  2. Internal sandhi (안쪽 결합): 옵코드 매개변수를 자동 변환
     단어 내부의 결합이 옵코드 인자를 변환.
     예: sat + cit + ānanda → sachcidānanda (3개 항 병합 → 단일 합성)

  3. Semantic integrity preservation through merge.
     결합 후에도 의미적 무결성을 보존.

고전적 예시:
  सच्चिदानन्द (sac-cid-ānanda) = sat + cit + ānanda
  "존재-의식-환희" (being-consciousness-bliss)의 결합.
  코드에서: exists(execute(bliss)) → merged_bliss_being_consciousness
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Optional

from flux_san.sandhi import (
    SandhiEngine,
    SandhiRule,
    SandhiToken,
    SandhiType,
    SandhiEffect,
)
from flux_san.vm import Opcode


# ═══════════════════════════════════════════════════════════════
# 코드 결합 유형
# ═══════════════════════════════════════════════════════════════

class MergeType(IntEnum):
    """코드 결합 유형."""
    FUNCTION_MERGE = auto()     # 두 함수 결합
    OPCODE_MERGE = auto()       # 두 옵코드 결합
    INTERFACE_ADAPT = auto()    # 인터페이스 적응
    PARAMETER_TRANSFORM = auto() # 매개변수 변환
    CONCEPT_FUSION = auto()     # 개념 융합 (sac-cid-ānanda 수준)


class MergeEffect(IntEnum):
    """결합 효과."""
    SEQUENTIAL = auto()   # 순차 실행 (a then b)
    PARALLEL = auto()     # 병렬 실행 (a and b)
    COMPOSED = auto()     # 합성 함수 (a ∘ b)
    MUTATED = auto()      # 변형 실행 (a transforms b)
    FUSED = auto()        # 완전 융합 (a and b become one)


# ═══════════════════════════════════════════════════════════════
# 결합된 코드 단위
# ═══════════════════════════════════════════════════════════════

@dataclass
class MergedCode:
    """결합된 코드 단위.

    Attributes:
        name: 결합된 이름
        source_names: 원래 소스 이름 목록
        merge_type: 결합 유형
        merge_effect: 결합 효과
        opcodes: 결합된 옵코드 시퀀스
        sandhi_type: 적용된 산디 유형
        semantic_preserved: 의미적 무결성 보존 여부
        integrity_score: 무결성 점수 (0.0 ~ 1.0)
    """
    name: str
    source_names: list[str] = field(default_factory=list)
    merge_type: MergeType = MergeType.FUNCTION_MERGE
    merge_effect: MergeEffect = MergeEffect.SEQUENTIAL
    opcodes: list[int] = field(default_factory=list)
    sandhi_type: SandhiType = SandhiType.NONE
    semantic_preserved: bool = True
    integrity_score: float = 1.0

    def __repr__(self) -> str:
        return (
            f"MergedCode({self.name!r}, "
            f"sources={self.source_names}, "
            f"type={self.merge_type.name}, "
            f"score={self.integrity_score:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
# 결합 이력
# ═══════════════════════════════════════════════════════════════

@dataclass
class MergeRecord:
    """결합 이력 기록."""
    source_a: str
    source_b: str
    merged: str
    sandhi_type: SandhiType
    merge_effect: MergeEffect
    integrity_before: float
    integrity_after: float

    @property
    def integrity_delta(self) -> float:
        return self.integrity_after - self.integrity_before

    def describe(self) -> str:
        return (
            f"{self.source_a} + {self.source_b} → {self.merged} "
            f"({self.sandhi_type.name}, δ={self.integrity_delta:+.2f})"
        )


# ═══════════════════════════════════════════════════════════════
# 개념 융합 정의 (Concept Fusion Registry)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ConceptFusion:
    """개념 융합 정의 — 고전적 산디 결합 패턴.

    예시: sat + cit + ānanda → sachcidānanda
    코드에서: exists(execute(bliss)) → single unified operation
    """
    components: list[str]        # 원래 구성요소
    fused: str                   # 융합된 형태
    meaning: str                # 의미
    opcodes: list[int] = field(default_factory=list)  # 생성되는 옵코드
    integrity_score: float = 1.0


# 사전에 정의된 개념 융합
_CONCEPT_FUSIONS: dict[str, ConceptFusion] = {
    "saccidānanda": ConceptFusion(
        components=["sat", "cit", "ānanda"],
        fused="saccidānanda",
        meaning="being-consciousness-bliss (सच्चिदानन्द)",
        opcodes=[Opcode.NOP, Opcode.CMP, Opcode.JMP],
        integrity_score=0.95,
    ),
    "satyam": ConceptFusion(
        components=["sat", "yam"],
        fused="satyam",
        meaning="truth/existence (सत्यम्)",
        opcodes=[Opcode.NOP, Opcode.STORE],
        integrity_score=0.90,
    ),
    "dharma": ConceptFusion(
        components=["dhṛ", "man"],
        fused="dharma",
        meaning="that which holds/sustains (धर्म)",
        opcodes=[Opcode.STORE, Opcode.JMP],
        integrity_score=0.85,
    ),
    "karma": ConceptFusion(
        components=["kṛ", "man"],
        fused="karma",
        meaning="action/deed (कर्म)",
        opcodes=[Opcode.CALL, Opcode.JMP],
        integrity_score=0.80,
    ),
    "yoga": ConceptFusion(
        components=["yuj", "gam"],
        fused="yoga",
        meaning="union/joining (योग)",
        opcodes=[Opcode.IADD, Opcode.CALL],
        integrity_score=0.90,
    ),
    "mokṣa": ConceptFusion(
        components=["muc", "kṣa"],
        fused="mokṣa",
        meaning="liberation/release (मोक्ष)",
        opcodes=[Opcode.MOV, Opcode.POP],
        integrity_score=0.85,
    ),
}


# ═══════════════════════════════════════════════════════════════
# SandhiCodeMerger
# ═══════════════════════════════════════════════════════════════

class SandhiCodeMerger:
    """산디 코드 병합기 — 음운 결합 규칙을 코드 병합으로.

    기존 SandhiEngine의 join/split 규칙을 활용하여:
      1. 두 코드 단위의 결합 (external sandhi)
      2. 코드 단위 내부 변환 (internal sandhi)
      3. 의미적 무결성 검증 및 보존

    Usage::

        merger = SandhiCodeMerger()

        # 두 함수 결합
        merged = merger.merge_functions(
            func_a="compute",
            func_b="store",
            opcodes_a=[Opcode.IADD, 0, 1, 2],
            opcodes_b=[Opcode.STORE, 0, 3],
        )

        # 개념 융합
        fusion = merger.lookup_concept_fusion("saccidānanda")
    """

    def __init__(self):
        self._engine = SandhiEngine()
        self._history: list[MergeRecord] = []
        self._fusions: dict[str, ConceptFusion] = dict(_CONCEPT_FUSIONS)

    # ── External Sandhi (함수 결합) ──

    def merge_functions(
        self,
        func_a: str,
        func_b: str,
        opcodes_a: list[int] | None = None,
        opcodes_b: list[int] | None = None,
    ) -> MergedCode:
        """External sandhi: 두 함수를 결합.

        산디 규칙이 결합된 이름과 인터페이스를 결정.

        Args:
            func_a: 첫 번째 함수 이름
            func_b: 두 번째 함수 이름
            opcodes_a: 첫 번째 함수의 옵코드 (없으면 NOP)
            opcodes_b: 두 번째 함수의 옵코드 (없으면 NOP)

        Returns:
            결합된 코드 단위
        """
        # 산디 결합으로 이름 생성
        merged_name = self._engine.join(func_a, func_b)

        # 결합 효과 결정
        merge_effect = self._determine_merge_effect(
            func_a, func_b, merged_name
        )

        # 옵코드 결합
        merged_opcodes = []
        if opcodes_a:
            merged_opcodes.extend(opcodes_a)
        if opcodes_b:
            merged_opcodes.extend(opcodes_b)

        # 무결성 점수 계산
        integrity = self._compute_integrity(func_a, func_b, merged_name)

        # 산디 유형 결정
        sandhi_type = self._detect_sandhi_type(func_a, func_b, merged_name)

        merged = MergedCode(
            name=merged_name,
            source_names=[func_a, func_b],
            merge_type=MergeType.FUNCTION_MERGE,
            merge_effect=merge_effect,
            opcodes=merged_opcodes,
            sandhi_type=sandhi_type,
            semantic_preserved=integrity > 0.5,
            integrity_score=integrity,
        )

        # 이력 기록
        self._history.append(MergeRecord(
            source_a=func_a,
            source_b=func_b,
            merged=merged_name,
            sandhi_type=sandhi_type,
            merge_effect=merge_effect,
            integrity_before=1.0,
            integrity_after=integrity,
        ))

        return merged

    # ── Internal Sandhi (옵코드 매개변수 변환) ──

    def merge_opcodes(
        self,
        opcodes_a: list[int],
        opcodes_b: list[int],
        label: str = "",
    ) -> MergedCode:
        """Internal sandhi: 두 옵코드 시퀀스를 결합.

        Args:
            opcodes_a: 첫 번째 옵코드 시퀀스
            opcodes_b: 두 번째 옵코드 시퀀스
            label: 레이블

        Returns:
            결합된 코드 단위
        """
        merged_ops = list(opcodes_a) + list(opcodes_b)

        # 결합 지점에서 중복 제거 최적화
        if len(opcodes_a) > 0 and len(opcodes_b) > 0:
            if opcodes_a[-1] == opcodes_b[0] == Opcode.NOP:
                merged_ops = list(opcodes_a) + list(opcodes_b[1:])
                merge_effect = MergeEffect.FUSED
            else:
                merge_effect = MergeEffect.SEQUENTIAL
        else:
            merge_effect = MergeEffect.SEQUENTIAL

        return MergedCode(
            name=label or f"merged_{len(self._history) + 1}",
            source_names=[f"seq_a", f"seq_b"],
            merge_type=MergeType.OPCODE_MERGE,
            merge_effect=merge_effect,
            opcodes=merged_ops,
            sandhi_type=SandhiType.INTERNAL,
            integrity_score=0.90,
        )

    # ── Concept Fusion (개념 융합) ──

    def lookup_concept_fusion(self, name: str) -> Optional[ConceptFusion]:
        """개념 융합 조회.

        Args:
            name: 융합된 이름 (예: "saccidānanda")

        Returns:
            개념 융합 정의 (없으면 None)
        """
        # 직접 매칭
        if name in self._fusions:
            return self._fusions[name]

        # 대소문자 무시 매칭
        name_lower = name.lower()
        for key, fusion in self._fusions.items():
            if key.lower() == name_lower:
                return fusion

        return None

    def create_concept_fusion(
        self,
        components: list[str],
        meaning: str = "",
        opcodes: list[int] | None = None,
    ) -> ConceptFusion:
        """새 개념 융합 생성.

        Args:
            components: 구성요소 목록
            meaning: 의미 설명
            opcodes: 생성되는 옵코드

        Returns:
            생성된 개념 융합
        """
        # 산디 결합으로 융합된 이름 생성
        if not components:
            return ConceptFusion(
                components=[], fused="", meaning=""
            )

        fused = components[0]
        for comp in components[1:]:
            fused = self._engine.join(fused, comp)

        fusion = ConceptFusion(
            components=components,
            fused=fused,
            meaning=meaning,
            opcodes=opcodes or [],
        )

        self._fusions[fused] = fusion
        return fusion

    def try_korean_cps_adaptation(
        self,
        korean_func_name: str,
        opcodes: list[int],
    ) -> MergedCode:
        """한국어-CPS 함수 인터페이스를 산디로 적응.

        산디 결합이 한국어-CPS 함수의 인터페이스를 자동으로 적응.
        이것이 한국-산스크리트 브리지의 핵심: 산디가 두 언어의
        코드 결합을 중재.

        Args:
            korean_func_name: 한국어 함수 이름
            opcodes: 옵코드 시퀀스

        Returns:
            적응된 코드 단위
        """
        # 한국어 함수명을 산디 형태로 변환
        # 예: "계산" → "gaesan" (음역)
        # 실제 구현에서는 더 정교한 음역이 필요하지만,
        # 핵심 아이디어는 산디 규칙이 적용됨

        # IAST 형태로 로마자화 (간이 버전)
        romanized = self._korean_to_romanized(korean_func_name)

        # 산디 결합으로 적응된 이름 생성
        if opcodes and len(opcodes) > 0:
            opcode_name = Opcode(opcodes[0]).name if opcodes[0] in Opcode._value2member_map_ else "op"
            adapted_name = self._engine.join(romanized, opcode_name.lower())
        else:
            adapted_name = romanized

        return MergedCode(
            name=adapted_name,
            source_names=[korean_func_name, "opcode_adapt"],
            merge_type=MergeType.INTERFACE_ADAPT,
            merge_effect=MergeEffect.MUTATED,
            opcodes=list(opcodes),
            sandhi_type=SandhiType.EXTERNAL,
            integrity_score=0.70,  # 크로스 언어이므로 낮은 점수
        )

    # ── 의미적 무결성 ──

    def _compute_integrity(
        self, source_a: str, source_b: str, merged: str
    ) -> float:
        """결합 후 의미적 무결성 점수 계산.

        기준:
          - 원본 요소가 보존되면 +0.3
          - 융합이 의미론적으로 일관되면 +0.4
          - 산디 규칙이 정확히 적용되면 +0.3
          - 결합 이름이 너무 짧으면 -0.2
        """
        score = 0.0

        # 원본 요소 보존
        a_preserved = source_a[:2] in merged if len(source_a) >= 2 else True
        b_preserved = source_b[:2] in merged if len(source_b) >= 2 else True
        if a_preserved and b_preserved:
            score += 0.3

        # 길이 적절성
        if 3 <= len(merged) <= len(source_a) + len(source_b):
            score += 0.4

        # 산디 규칙 적용 확인
        if merged != source_a + source_b:
            score += 0.3  # 실제 산디 변환 발생

        # 너무 짧은 결합 패널티
        if len(merged) < 3:
            score -= 0.2

        return max(0.0, min(1.0, score))

    def _determine_merge_effect(
        self, source_a: str, source_b: str, merged: str
    ) -> MergeEffect:
        """결합 효과를 결정."""
        if merged == source_a + source_b:
            return MergeEffect.SEQUENTIAL
        if len(merged) < len(source_a) + len(source_b):
            return MergeEffect.FUSED
        return MergeEffect.COMPOSED

    def _detect_sandhi_type(
        self, source_a: str, source_b: str, merged: str
    ) -> SandhiType:
        """적용된 산디 유형 감지."""
        # 모음 산디 패턴
        vowel_pairs = [
            ("a", "a"), ("i", "a"), ("u", "a"),
            ("a", "i"), ("a", "u"), ("i", "i"), ("u", "u"),
        ]
        for v1, v2 in vowel_pairs:
            if source_a.endswith(v1) and source_b.startswith(v2):
                return SandhiType.VOWEL

        # 장음 결합
        long_vowels = ["ā", "ī", "ū", "e", "o"]
        for lv in long_vowels:
            if lv in merged and lv not in source_a + source_b:
                return SandhiType.VOWEL

        # 자음 결합
        consonant_clusters = ["kṣ", "ñj", "tth", "cch"]
        for cc in consonant_clusters:
            if cc in merged:
                return SandhiType.CONSONANT

        return SandhiType.EXTERNAL

    def _korean_to_romanized(self, korean: str) -> str:
        """한국어 텍스트를 간이 로마자화.

        실제 구현에서는 더 정교한 음역이 필요.
        여기서는 핵심 아이디어를 보여주기 위한 간이 버전.
        """
        # 초성-중성-종성을 로마자로 매핑 (최소한 버전)
        simple_map = {
            "가": "ga", "나": "na", "다": "da", "라": "la", "마": "ma",
            "바": "ba", "사": "sa", "아": "a", "자": "ja", "차": "cha",
            "카": "ka", "타": "ta", "파": "pa", "하": "ha",
            "계": "gye", "산": "san", "연": "yeon", "동": "dong",
            "성": "seong", "수": "su", "전": "jeon",
        }
        result = ""
        i = 0
        while i < len(korean):
            matched = False
            # 긴 음절 매칭 시도
            for syllable, roman in sorted(simple_map.items(), key=len, reverse=True):
                if korean[i:i+len(syllable)] == syllable:
                    result += roman
                    i += len(syllable)
                    matched = True
                    break
            if not matched:
                result += korean[i].lower()
                i += 1
        return result

    # ── 이력 및 조회 ──

    @property
    def merge_history(self) -> list[MergeRecord]:
        """결합 이력."""
        return list(self._history)

    @property
    def known_fusions(self) -> dict[str, ConceptFusion]:
        """등록된 개념 융합."""
        return dict(self._fusions)

    def describe_last_merge(self) -> str:
        """마지막 결합을 설명."""
        if not self._history:
            return "(no merges yet)"
        return self._history[-1].describe()

    def fusion_table(self) -> str:
        """개념 융합 테이블."""
        lines = [
            "╔═══════════════════════════════════════════════════════════════╗",
            "║  Sandhi Code Mergers — Concept Fusion Registry                    ║",
            "║  सन्धि-कोड-मर्जनम् — Concept Fusion Register               ║",
            "╠════════════════════╦════════════════════╦═══════════════════════╣",
            "║ Fused Form        ║ Components             ║ Meaning             ║",
            "╠════════════════════╬════════════════════╬═══════════════════════╣",
        ]
        for name, fusion in sorted(self._fusions.items()):
            components = " + ".join(fusion.components)
            lines.append(
                f"║ {name:<18s} ║ {components:<22s} ║ {fusion.meaning:<21s} ║"
            )
        lines.append("╚════════════════════╩════════════════════╩═══════════════════════╝")
        return "\n".join(lines)
