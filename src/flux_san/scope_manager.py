"""
VibhaktiScopeManager — 8-Case Scope Nesting & Transition System
=================================================================

확장된 비박티(Vibhakti) 범위 관리자.

기존 vibhakti.py의 8-케이스 시스템을 확장하여:
  1. 완전한 8-케이스 hex 범위 코드 매핑
  2. 범위 중첩 (Scope Nesting): 장소 격(genitive 안의 locative = 패키지 안의 모듈)
  3. 범위 전이 (Scope Transitions): 명사의 격이 바뀌면 범위가 전이됨
  4. A2A를 위한 8번째 격(sambodhana/vocative) = 에이전트 호출

범위 코드:
  1st prathamā (nominative)  → SCOPE_GLOBAL      (0x01)
  2nd dvitīyā (accusative)  → SCOPE_VALUE       (0x02)
  3rd tṛtīyā (instrumental) → SCOPE_TOOL        (0x03)
  4th caturthī (dative)      → SCOPE_OUTPUT      (0x04)
  5th pañcamī (ablative)     → SCOPE_SOURCE      (0x05)
  6th ṣaṣṭhī (genitive)    → SCOPE_OWNERSHIP   (0x06)
  7th saptamī (locative)     → SCOPE_CONTAINER   (0x07)
  8th sambodhana (vocative)  → SCOPE_AGENT_INVOKE (0x08) — A2A!
"""

from __future__ import annotations

from enum import IntEnum, auto
from dataclasses import dataclass, field
from typing import Optional

from flux_san.vibhakti import (
    Vibhakti,
    ScopeLevel,
    VibhaktiValidator,
    ScopedAccess,
)


# ═══════════════════════════════════════════════════════════════
# 확장 범위 코드 (16진수)
# ═══════════════════════════════════════════════════════════════

class ScopeCode(IntEnum):
    """비박티 기반 범위 코드 — 8 격이 8개의 범위를 정의.

    명시적 비트 마스크로 범위 조합이 가능.
    """
    SCOPE_NONE           = 0x00  # 범위 없음
    SCOPE_GLOBAL         = 0x01  # 1st prathamā (nominative) — 전역 공용
    SCOPE_VALUE          = 0x02  # 2nd dvitīyā (accusative) — 값 전달
    SCOPE_TOOL           = 0x03  # 3rd tṛtīyā (instrumental) — 도구/함수
    SCOPE_OUTPUT         = 0x04  # 4th caturthī (dative) — 출력/권한 부여
    SCOPE_SOURCE         = 0x05  # 5th pañcamī (ablative) — 입력/출처
    SCOPE_OWNERSHIP      = 0x06  # 6th ṣaṣṭhī (genitive) — 소유/속성
    SCOPE_CONTAINER      = 0x07  # 7th saptamī (locative) — 컨테이너/영역
    SCOPE_AGENT_INVOKE   = 0x08  # 8th sambodhana (vocative) — A2A 호출!

    # 복합 범위 (비트 조합)
    SCOPE_READ_ONLY      = 0x01 | 0x02  # 읽기 전용 (nominative + accusative)
    SCOPE_READ_WRITE     = 0x01 | 0x02 | 0x06  # 읽기+쓰기 (+ ownership)
    SCOPE_FULL_ACCESS    = 0xFF  # 전체 접근


# Vibhakti → ScopeCode 매핑
_VIBHAKTI_SCOPE_CODE: dict[Vibhakti, ScopeCode] = {
    Vibhakti.PRATHAMA:   ScopeCode.SCOPE_GLOBAL,
    Vibhakti.DVITIYA:    ScopeCode.SCOPE_VALUE,
    Vibhakti.TRITIYA:    ScopeCode.SCOPE_TOOL,
    Vibhakti.CHATURTHI:  ScopeCode.SCOPE_OUTPUT,
    Vibhakti.PANCHAMI:   ScopeCode.SCOPE_SOURCE,
    Vibhakti.SHASHTHI:   ScopeCode.SCOPE_OWNERSHIP,
    Vibhakti.SAPTAMI:    ScopeCode.SCOPE_CONTAINER,
    Vibhakti.SAMBODHANA: ScopeCode.SCOPE_AGENT_INVOKE,
}

# ScopeCode → 설명
_SCOPE_DESCRIPTIONS: dict[ScopeCode, str] = {
    ScopeCode.SCOPE_GLOBAL:       "1st prathamā (nominative) — 전역 공용 범위",
    ScopeCode.SCOPE_VALUE:        "2nd dvitīyā (accusative) — 값/인자 전달 범위",
    ScopeCode.SCOPE_TOOL:         "3rd tṛtīyā (instrumental) — 도구/함수 호출 범위",
    ScopeCode.SCOPE_OUTPUT:       "4th caturthī (dative) — 출력/권한 부여 범위",
    ScopeCode.SCOPE_SOURCE:       "5th pañcamī (ablative) — 입력/출처 범위",
    ScopeCode.SCOPE_OWNERSHIP:    "6th ṣaṣṭhī (genitive) — 소유/속성 범위",
    ScopeCode.SCOPE_CONTAINER:    "7th saptamī (locative) — 컨테이너/영역 범위",
    ScopeCode.SCOPE_AGENT_INVOKE: "8th sambodhana (vocative) — A2A 에이전트 호출",
}


# ═══════════════════════════════════════════════════════════════
# 범위 중첩 프레임
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScopeFrame:
    """범위 프레임 — 단일 범위 수준의 실행 컨텍스트.

    Attributes:
        vibhakti: 비박티 (문법 격)
        scope_code: 범위 코드
        noun: 이 범위에 있는 명사
        parent: 부모 프레임 (중첩)
        depth: 중첩 깊이
        agent: 소유 에이전트 (A2A용)
        region: 영역 ID (locative용)
    """
    vibhakti: Vibhakti
    scope_code: ScopeCode
    noun: str = ""
    parent: Optional[ScopeFrame] = None
    depth: int = 0
    agent: str = ""
    region: int = 0

    @property
    def description(self) -> str:
        return _SCOPE_DESCRIPTIONS.get(self.scope_code, "unknown")

    def effective_scope(self) -> int:
        """유효 범위 — 부모 범위까지 OR 결합."""
        mask = self.scope_code.value
        p = self.parent
        while p is not None:
            mask |= p.scope_code.value
            p = p.parent
        return mask

    def is_inside(self, outer_scope: ScopeCode) -> bool:
        """이 프레임이 특정 범위 안에 있는지."""
        effective = self.effective_scope()
        return bool(effective & outer_scope.value)

    def __repr__(self) -> str:
        return (
            f"ScopeFrame({self.vibhakti.devanagari}, "
            f"noun={self.noun!r}, depth={self.depth})"
        )


# ═══════════════════════════════════════════════════════════════
# 범위 전이 기록
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScopeTransition:
    """범위 전이 기록 — 명사의 격이 바뀔 때의 전이.

    예시: rāmaḥ → rāmāya (nominative → dative)
    "라마"가 주어에서 수혜자로 전이.
    """
    noun: str
    from_vibhakti: Vibhakti
    to_vibhakti: Vibhakti
    from_scope: ScopeCode
    to_scope: ScopeCode

    @property
    def is_escalation(self) -> bool:
        """범위가 확대되는 전이인지."""
        return self.to_scope.value > self.from_scope.value

    @property
    def is_demotion(self) -> bool:
        """범위가 축소되는 전이인지."""
        return self.to_scope.value < self.from_scope.value

    @property
    def is_a2a_transition(self) -> bool:
        """A2A 관련 전이인지 (8th case 관련)."""
        return (self.from_vibhakti == Vibhakti.SAMBODHANA or
                self.to_vibhakti == Vibhakti.SAMBODHANA)

    def describe(self) -> str:
        return (
            f"{self.noun}: {self.from_vibhakti.devanagari} → "
            f"{self.to_vibhakti.devanagari} "
            f"(0x{self.from_scope.value:02X} → 0x{self.to_scope.value:02X})"
        )


# ═══════════════════════════════════════════════════════════════
# 범위 관리자
# ═══════════════════════════════════════════════════════════════

class VibhaktiScopeManager:
    """비박티 범위 관리자 — 8-케이스 범위 시스템의 핵심.

    기능:
      1. 범위 중첩: locative 안의 genitive = 패키지 안의 모듈
      2. 범위 전이: 명사의 격이 바뀌면 범위 전이 기록
      3. 유효 범위 계산: 중첩된 범위의 OR 결합
      4. A2A 호출: 8번째 격(sambodhana)으로 에이전트 호출

    Usage::

        mgr = VibhaktiScopeManager()

        # 범위 프레임 생성
        mgr.push_frame("rāmaḥ", Vibhakti.PRATHAMA)
        mgr.push_frame("grāme", Vibhakti.SAPTAMI)
        # → genitive 안의 locative = 패키지 안의 모듈

        # 범위 전이
        mgr.transition("rāmaḥ", Vibhakti.PRATHAMA, Vibhakti.CHATURTHI)
        # → nominative → dative: 주어에서 수혜자로
    """

    def __init__(self) -> None:
        self._frame_stack: list[ScopeFrame] = []
        self._transitions: list[ScopeTransition] = []
        self._noun_scopes: dict[str, Vibhakti] = {}  # 명사 → 현재 격
        self._history: list[str] = []

    # ── 프레임 관리 ──

    def push_frame(
        self,
        noun: str,
        vibhakti: Vibhakti,
        agent: str = "",
        region: int = 0,
    ) -> ScopeFrame:
        """범위 프레임을 스택에 푸시.

        Args:
            noun: 명사 (격변화된 형태)
            vibhakti: 문법 격
            agent: 소유 에이전트
            region: 영역 ID

        Returns:
            생성된 프레임
        """
        scope_code = _VIBHAKTI_SCOPE_CODE.get(vibhakti, ScopeCode.SCOPE_NONE)
        parent = self._frame_stack[-1] if self._frame_stack else None

        frame = ScopeFrame(
            vibhakti=vibhakti,
            scope_code=scope_code,
            noun=noun,
            parent=parent,
            depth=len(self._frame_stack),
            agent=agent,
            region=region,
        )

        # 이전 격 기록 → 전이 감지
        if noun in self._noun_scopes:
            old_vibhakti = self._noun_scopes[noun]
            if old_vibhakti != vibhakti:
                self._record_transition(noun, old_vibhakti, vibhakti)

        self._noun_scopes[noun] = vibhakti
        self._frame_stack.append(frame)
        self._history.append(f"PUSH {frame}")

        return frame

    def pop_frame(self) -> Optional[ScopeFrame]:
        """범위 프레임을 스택에서 팝."""
        if self._frame_stack:
            frame = self._frame_stack.pop()
            self._history.append(f"POP {frame}")
            return frame
        return None

    @property
    def current_frame(self) -> Optional[ScopeFrame]:
        """현재 범위 프레임."""
        return self._frame_stack[-1] if self._frame_stack else None

    @property
    def depth(self) -> int:
        """현재 범위 중첩 깊이."""
        return len(self._frame_stack)

    @property
    def effective_scope(self) -> int:
        """현재 유효 범위 마스크 (모든 중첩 OR)."""
        mask = 0
        for frame in self._frame_stack:
            mask |= frame.scope_code.value
        return mask

    @property
    def frames(self) -> list[ScopeFrame]:
        """모든 프레임 (순서대로)."""
        return list(self._frame_stack)

    # ── 범위 전이 ──

    def transition(
        self,
        noun: str,
        from_vibhakti: Vibhakti,
        to_vibhakti: Vibhakti,
    ) -> ScopeTransition:
        """범위 전이를 기록하고 수행.

        명사의 격이 바뀌면 범위가 전이됨.
        예: rāmaḥ → rāmāya (nominative → dative)

        Args:
            noun: 명사
            from_vibhakti: 원래 격
            to_vibhakti: 새 격

        Returns:
            전이 기록
        """
        from_scope = _VIBHAKTI_SCOPE_CODE.get(from_vibhakti, ScopeCode.SCOPE_NONE)
        to_scope = _VIBHAKTI_SCOPE_CODE.get(to_vibhakti, ScopeCode.SCOPE_NONE)

        trans = ScopeTransition(
            noun=noun,
            from_vibhakti=from_vibhakti,
            to_vibhakti=to_vibhakti,
            from_scope=from_scope,
            to_scope=to_scope,
        )

        self._transitions.append(trans)
        self._noun_scopes[noun] = to_vibhakti
        self._history.append(f"TRANSITION {trans.describe()}")

        return trans

    def _record_transition(
        self, noun: str, from_v: Vibhakti, to_v: Vibhakti
    ) -> None:
        """내부 전이 기록."""
        self.transition(noun, from_v, to_v)

    @property
    def transitions(self) -> list[ScopeTransition]:
        """모든 전이 기록."""
        return list(self._transitions)

    # ── 범위 검사 ──

    def check_access(self, required_scope: ScopeCode) -> bool:
        """현재 유효 범위가 필요한 범위를 포함하는지."""
        return bool(self.effective_scope & required_scope.value)

    def check_frame_access(self, frame: ScopeFrame, required: ScopeCode) -> bool:
        """특정 프레임의 유효 범위 검사."""
        return bool(frame.effective_scope() & required.value)

    def requires_a2a(self) -> bool:
        """현재 범위가 A2A 호출을 필요로 하는지 (8th case)."""
        return bool(self.effective_scope & ScopeCode.SCOPE_AGENT_INVOKE.value)

    # ── 중첩 예시 ──

    def describe_nesting(self) -> str:
        """현재 범위 중첩 구조를 설명."""
        if not self._frame_stack:
            return "(empty scope stack)"

        lines = []
        for i, frame in enumerate(self._frame_stack):
            indent = "  " * frame.depth
            lines.append(
                f"{indent}[{i}] {frame.vibhakti.devanagari}/{frame.vibhakti.iast} "
                f"(0x{frame.scope_code.value:02X}) — {frame.noun}"
            )
        return "\n".join(lines)

    # ── 테이블 ──

    def scope_table(self) -> str:
        """8-케이스 범위 매핑 테이블."""
        lines = [
            "╔══════════════════════════════════════════════════════════════════╗",
            "║  Aṣṭau-vibhakti — 8-Case Scope System (Extended)               ║",
            "║  अष्टौ-विभक्तयः — FLUX Scope Codes                            ║",
            "╠══════╦═══════════════╦════════════════╦═══════════╦═════════════╣",
            "║ Case  ║ Sanskrit    ║ English         ║ Hex Code ║ FLUX Scope  ║",
            "╠══════╬═══════════════╬════════════════╬═══════════╬═════════════╣",
        ]
        for v in Vibhakti:
            sc = _VIBHAKTI_SCOPE_CODE.get(v, ScopeCode.SCOPE_NONE)
            scope_name = sc.name if sc != ScopeCode.SCOPE_NONE else "?"
            a2a_marker = " ← A2A!" if v == Vibhakti.SAMBODHANA else ""
            lines.append(
                f"║  {v.value:>2}   ║ {v.devanagari:<13s} ║ {v.english:<16s} "
                f"║ 0x{sc.value:02X}     ║ {scope_name:<11s}{a2a_marker} ║"
            )
        lines.append("╚══════╩═══════════════╩════════════════╩═══════════╩═════════════╝")
        return "\n".join(lines)

    def clear(self) -> None:
        """상태 초기화."""
        self._frame_stack.clear()
        self._transitions.clear()
        self._noun_scopes.clear()
        self._history.clear()

    def __len__(self) -> int:
        return self.depth

    def __repr__(self) -> str:
        return (
            f"VibhaktiScopeManager(depth={self.depth}, "
            f"effective=0x{self.effective_scope:04X})"
        )
