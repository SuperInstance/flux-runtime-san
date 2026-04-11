"""
FluxInterpreterSan — Sanskrit-first NL Interpreter for FLUX VM
================================================================

Translates Sanskrit natural-language commands into FLUX bytecode patterns.

Supported patterns (IAST for matching, Devanāgarī for display):
  ───────────────────────────────────────────────────────────────
  गणय $a प्लुत $b         → gaṇaya a pluta b          → IADD
  $a गुण $b               → a guṇa b                  → IMUL
  $a शोष $b               → a śoṣa b                  → ISUB
  $a भाज $b               → a bhāj b                  → IDIV
  $a इतः $b पर्यन्तयोगः  → a itaḥ b paryantayogaḥ    → range sum
  लोड $reg सह $val        → load Rn saha val           → MOVI
  संस्कृत $text           → saṃskṛta text              → PRINT
  विराम                    → virāma                    → HALT
  $a तुल्य $b              → a tulya b                 → CMP/ICMP

Sandhi resolution for compound word splitting.
Dual number (dvivacana) support for pairwise operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from flux_san.vibhakti import Vibhakti, VibhaktiValidator, ScopedAccess, ScopeLevel
from flux_san.lakara import Lakara, LakaraDetector, LakaraContext, ExecutionMode
from flux_san.samasa import SamasaParser, SamasaType, Compound


# ---------------------------------------------------------------------------
# FLUX VM — minimal Python reimplementation (64-register, stack-based)
# Matches the TypeScript flux/lib/flux/vm.ts ISA exactly.
# ---------------------------------------------------------------------------

class Op:
    """FLUX Bytecode Opcodes — variable-length encoding."""
    NOP           = 0x00
    MOV           = 0x01
    LOAD          = 0x02
    STORE         = 0x03
    JMP           = 0x04
    JZ            = 0x05
    JNZ           = 0x06
    CALL          = 0x07
    IADD          = 0x08
    ISUB          = 0x09
    IMUL          = 0x0A
    IDIV          = 0x0B
    IMOD          = 0x0C
    INEG          = 0x0D
    INC           = 0x0E
    DEC           = 0x0F
    IAND          = 0x10
    IOR           = 0x11
    IXOR          = 0x12
    INOT          = 0x13
    ICMP          = 0x18
    IEQ           = 0x19
    ILT           = 0x1A
    ILE           = 0x1B
    IGT           = 0x1C
    IGE           = 0x1D
    TEST          = 0x1E
    PUSH          = 0x20
    POP           = 0x21
    DUP           = 0x22
    SWAP          = 0x23
    ROT           = 0x24
    RET           = 0x28
    CALL_IND      = 0x29
    MOVI          = 0x2B
    CMP           = 0x2D
    JE            = 0x2E
    JNE           = 0x2F
    FADD          = 0x40
    FSUB          = 0x41
    FMUL          = 0x42
    FDIV          = 0x43
    PRINT         = 0xFE
    HALT          = 0xFF

    # A2A Agent Protocol
    TELL          = 0x60
    ASK           = 0x61
    DELEGATE      = 0x62
    BROADCAST     = 0x63
    TRUST_CHECK   = 0x64
    CAPABILITY_REQ = 0x65


OP_NAMES: dict[int, str] = {
    0x00: "NOP", 0x01: "MOV", 0x02: "LOAD", 0x03: "STORE",
    0x04: "JMP", 0x05: "JZ", 0x06: "JNZ", 0x07: "CALL",
    0x08: "IADD", 0x09: "ISUB", 0x0A: "IMUL", 0x0B: "IDIV",
    0x0C: "IMOD", 0x0D: "INEG", 0x0E: "INC", 0x0F: "DEC",
    0x10: "IAND", 0x11: "IOR", 0x12: "IXOR", 0x13: "INOT",
    0x18: "ICMP", 0x19: "IEQ", 0x1A: "ILT", 0x1B: "ILE",
    0x1C: "IGT", 0x1D: "IGE", 0x1E: "TEST",
    0x20: "PUSH", 0x21: "POP", 0x22: "DUP", 0x23: "SWAP", 0x24: "ROT",
    0x28: "RET", 0x29: "CALL_IND", 0x2B: "MOVI",
    0x2D: "CMP", 0x2E: "JE", 0x2F: "JNE",
    0x40: "FADD", 0x41: "FSUB", 0x42: "FMUL", 0x43: "FDIV",
    0x60: "TELL", 0x61: "ASK", 0x62: "DELEGATE",
    0x63: "BROADCAST", 0x64: "TRUST_CHECK", 0x65: "CAP_REQ",
    0xFE: "PRINT", 0xFF: "HALT",
}


@dataclass
class VMState:
    """Snapshot of VM state."""
    registers: list[int]
    flags_zero: bool = False
    flags_negative: bool = False
    stack: list[int] = field(default_factory=list)
    pc: int = 0
    halted: bool = False
    cycles: int = 0
    error: str | None = None


@dataclass
class ExecutionResult:
    """Result of VM execution."""
    success: bool
    result: int = 0
    registers: list[int] = field(default_factory=lambda: [0] * 64)
    cycles: int = 0
    error: str | None = None
    halted: bool = False
    trace: list[str] = field(default_factory=list)


class FluxVM:
    """
    Minimal FLUX Virtual Machine — 64-register, stack-based.
    Matches the TypeScript reference implementation.
    """

    def __init__(self, bytecode: bytearray | None = None, max_cycles: int = 1_000_000,
                 trace: bool = False):
        self.bytecode = bytecode or bytearray()
        self.max_cycles = max_cycles
        self.trace = trace
        self.regs: list[int] = [0] * 64
        self.flags_zero = False
        self.flags_negative = False
        self.stack: list[int] = []
        self.pc = 0
        self.halted = False
        self.error: str | None = None
        self.cycles = 0
        self.trace_log: list[str] = []

    def read_reg(self, r: int) -> int:
        return self.regs[r] if 0 <= r < 64 else 0

    def write_reg(self, r: int, val: int) -> None:
        if 0 <= r < 64:
            self.regs[r] = val & 0xFFFFFFFF if val >= 0 else val

    def push(self, val: int) -> None:
        self.stack.append(val)

    def pop(self) -> int:
        return self.stack.pop() if self.stack else 0

    def _update_flags(self, result: int) -> None:
        self.flags_zero = result == 0
        self.flags_negative = result < 0

    def _read_u16(self, offset: int) -> int:
        if offset + 1 < len(self.bytecode):
            return self.bytecode[offset] | (self.bytecode[offset + 1] << 8)
        return 0

    def _log(self, msg: str) -> None:
        if self.trace:
            self.trace_log.append(msg)

    def get_state(self) -> VMState:
        return VMState(
            registers=list(self.regs),
            flags_zero=self.flags_zero,
            flags_negative=self.flags_negative,
            stack=list(self.stack),
            pc=self.pc,
            halted=self.halted,
            cycles=self.cycles,
            error=self.error,
        )

    def execute(self) -> ExecutionResult:
        bc = self.bytecode

        while self.pc < len(bc) and not self.halted and self.cycles < self.max_cycles:
            op = bc[self.pc]
            self.cycles += 1

            match op:
                case Op.NOP:
                    self.pc += 1
                case Op.MOV:
                    if self.pc + 2 < len(bc):
                        self.write_reg(bc[self.pc + 1], self.read_reg(bc[self.pc + 2]))
                    self.pc += 3
                case Op.LOAD:
                    if self.pc + 2 < len(bc):
                        self.write_reg(bc[self.pc + 1], self.read_reg(bc[self.pc + 2]))
                    self.pc += 3
                case Op.STORE:
                    if self.pc + 2 < len(bc):
                        self.write_reg(bc[self.pc + 2], self.read_reg(bc[self.pc + 1]))
                    self.pc += 3
                case Op.MOVI:
                    if self.pc + 3 < len(bc):
                        r = bc[self.pc + 1]
                        imm = self._read_u16(self.pc + 2)
                        val = imm - 65536 if imm > 32767 else imm
                        self.write_reg(r, val)
                        self._update_flags(val)
                    self.pc += 4
                case Op.IADD:
                    if self.pc + 3 < len(bc):
                        rd, ra, rb = bc[self.pc + 1], bc[self.pc + 2], bc[self.pc + 3]
                        result = self.read_reg(ra) + self.read_reg(rb)
                        self.write_reg(rd, result)
                        self._update_flags(result)
                    self.pc += 4
                case Op.ISUB:
                    if self.pc + 3 < len(bc):
                        rd, ra, rb = bc[self.pc + 1], bc[self.pc + 2], bc[self.pc + 3]
                        result = self.read_reg(ra) - self.read_reg(rb)
                        self.write_reg(rd, result)
                        self._update_flags(result)
                    self.pc += 4
                case Op.IMUL:
                    if self.pc + 3 < len(bc):
                        rd, ra, rb = bc[self.pc + 1], bc[self.pc + 2], bc[self.pc + 3]
                        result = self.read_reg(ra) * self.read_reg(rb)
                        self.write_reg(rd, result)
                        self._update_flags(result)
                    self.pc += 4
                case Op.IDIV:
                    if self.pc + 3 < len(bc):
                        rd, ra, rb = bc[self.pc + 1], bc[self.pc + 2], bc[self.pc + 3]
                        divisor = self.read_reg(rb)
                        if divisor == 0:
                            self.error = "Division by zero (शून्येन भाजने दोषः)"
                            self.halted = True
                        else:
                            result = int(self.read_reg(ra) / divisor)
                            self.write_reg(rd, result)
                            self._update_flags(result)
                    self.pc += 4
                case Op.IMOD:
                    if self.pc + 3 < len(bc):
                        rd, ra, rb = bc[self.pc + 1], bc[self.pc + 2], bc[self.pc + 3]
                        divisor = self.read_reg(rb)
                        if divisor == 0:
                            self.error = "Modulo by zero"
                            self.halted = True
                        else:
                            result = self.read_reg(ra) % divisor
                            self.write_reg(rd, result)
                            self._update_flags(result)
                    self.pc += 4
                case Op.INEG:
                    if self.pc + 1 < len(bc):
                        r = bc[self.pc + 1]
                        result = -self.read_reg(r)
                        self.write_reg(r, result)
                        self._update_flags(result)
                    self.pc += 2
                case Op.INC:
                    if self.pc + 1 < len(bc):
                        r = bc[self.pc + 1]
                        result = self.read_reg(r) + 1
                        self.write_reg(r, result)
                        self._update_flags(result)
                    self.pc += 2
                case Op.DEC:
                    if self.pc + 1 < len(bc):
                        r = bc[self.pc + 1]
                        result = self.read_reg(r) - 1
                        self.write_reg(r, result)
                        self._update_flags(result)
                    self.pc += 2
                case Op.ICMP:
                    if self.pc + 2 < len(bc):
                        a, b = self.read_reg(bc[self.pc + 1]), self.read_reg(bc[self.pc + 2])
                        self.flags_zero = a == b
                        self.flags_negative = a < b
                    self.pc += 3
                case Op.CMP:
                    if self.pc + 2 < len(bc):
                        diff = self.read_reg(bc[self.pc + 1]) - self.read_reg(bc[self.pc + 2])
                        self._update_flags(diff)
                    self.pc += 3
                case Op.PUSH:
                    if self.pc + 1 < len(bc):
                        self.push(self.read_reg(bc[self.pc + 1]))
                    self.pc += 2
                case Op.POP:
                    if self.pc + 1 < len(bc):
                        self.write_reg(bc[self.pc + 1], self.pop())
                    self.pc += 2
                case Op.DUP:
                    if self.stack:
                        self.push(self.stack[-1])
                    self.pc += 2
                case Op.SWAP:
                    if len(self.stack) >= 2:
                        self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
                    self.pc += 2
                case Op.JMP:
                    addr = self._read_u16(self.pc + 1)
                    self.pc = addr
                case Op.JZ:
                    if self.pc + 3 < len(bc):
                        r, addr = bc[self.pc + 1], self._read_u16(self.pc + 2)
                        self.pc = addr if self.read_reg(r) == 0 else self.pc + 4
                    else:
                        self.pc += 4
                case Op.JNZ:
                    if self.pc + 3 < len(bc):
                        r, addr = bc[self.pc + 1], self._read_u16(self.pc + 2)
                        self.pc = addr if self.read_reg(r) != 0 else self.pc + 4
                    else:
                        self.pc += 4
                case Op.JE:
                    addr = self._read_u16(self.pc + 1)
                    self.pc = addr if self.flags_zero else self.pc + 3
                case Op.JNE:
                    addr = self._read_u16(self.pc + 1)
                    self.pc = addr if not self.flags_zero else self.pc + 3
                case Op.PRINT:
                    if self.pc + 1 < len(bc):
                        val = self.read_reg(bc[self.pc + 1])
                        self._log(f"PRINT R{bc[self.pc + 1]} = {val}")
                        self._print_output = val
                    self.pc += 2
                case Op.HALT:
                    self.halted = True
                    self.pc += 1
                case Op.RET:
                    self.halted = True
                    self.pc += 1
                case _:
                    self.pc += 1

        if self.cycles >= self.max_cycles and not self.halted:
            self.error = "Max cycles exceeded (चक्रसीमातिक्रमः)"

        return ExecutionResult(
            success=self.error is None,
            result=self.regs[0],
            registers=list(self.regs),
            cycles=self.cycles,
            error=self.error,
            halted=self.halted,
            trace=self.trace_log,
        )


# ---------------------------------------------------------------------------
# Sanskrit NL Pattern Definitions
# ---------------------------------------------------------------------------

@dataclass
class SanskritPattern:
    """A Sanskrit NL → bytecode translation pattern."""
    name: str                # Pattern name (English)
    devanagari: str          # Pattern template in Devanāgarī
    iast_template: str       # Pattern template in IAST
    regex: re.Pattern        # Compiled regex for matching (IAST)
    bytecode_fn: Any         # Function: (match) → bytearray
    description: str = ""    # Description


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------

class FluxInterpreterSan:
    """
    Sanskrit-first natural language interpreter for the FLUX VM.

    Translates Sanskrit (IAST) input into FLUX bytecode and executes it.
    Supports sandhi resolution, vibhakti scope control, and lakāra execution modes.
    """

    def __init__(self, trace: bool = False, default_lakara: Lakara = Lakara.LAT):
        self.vm = FluxVM(trace=trace)
        self.trace = trace
        self.default_lakara = default_lakara
        self.lakara_context = LakaraDetector.make_context(default_lakara)
        self._print_output: int | None = None
        self._patterns = self._build_patterns()
        self._history: list[str] = []
        self._symbols: dict[str, int] = {}  # Named registers / variables

    @property
    def registers(self) -> list[int]:
        return self.vm.regs

    @property
    def print_output(self) -> int | None:
        return getattr(self, '_print_output', None)

    def _build_patterns(self) -> list[SanskritPattern]:
        """Build the Sanskrit NL pattern list."""
        return [
            # गणय $a प्लुत $b → gaṇaya a pluta b → IADD R0, R_a, R_b
            SanskritPattern(
                name="add",
                devanagari="गणय $a प्लुत $b",
                iast_template="gaṇaya {a} pluta {b}",
                regex=re.compile(
                    r"gaṇaya\s+(?P<a>\S+)\s+pluta\s+(?P<b>\S+)", re.IGNORECASE
                ),
                bytecode_fn=self._bc_add,
                description="Addition (योगः) — gaṇaya a pluta b",
            ),
            # $a गुण $b → a guṇa b → IMUL R0, R_a, R_b
            SanskritPattern(
                name="multiply",
                devanagari="$a गुण $b",
                iast_template="{a} guṇa {b}",
                regex=re.compile(
                    r"(?P<a>\S+)\s+guṇa\s+(?P<b>\S+)", re.IGNORECASE
                ),
                bytecode_fn=self._bc_mul,
                description="Multiplication (गुणनम्) — a guṇa b",
            ),
            # $a शोष $b → a śoṣa b → ISUB R0, R_a, R_b
            SanskritPattern(
                name="subtract",
                devanagari="$a शोष $b",
                iast_template="{a} śoṣa {b}",
                regex=re.compile(
                    r"(?P<a>\S+)\s+śoṣa\s+(?P<b>\S+)", re.IGNORECASE
                ),
                bytecode_fn=self._bc_sub,
                description="Subtraction (व्यवकलनम्) — a śoṣa b",
            ),
            # $a भाज $b → a bhāj b → IDIV R0, R_a, R_b
            SanskritPattern(
                name="divide",
                devanagari="$a भाज $b",
                iast_template="{a} bhāj {b}",
                regex=re.compile(
                    r"(?P<a>\S+)\s+bhāj\s+(?P<b>\S+)", re.IGNORECASE
                ),
                bytecode_fn=self._bc_div,
                description="Division (भाजनम्) — a bhāj b",
            ),
            # $a इतः $b पर्यन्तयोगः → range sum from a to b
            SanskritPattern(
                name="range_sum",
                devanagari="$a इतः $b पर्यन्तयोगः",
                iast_template="{a} itaḥ {b} paryantayogaḥ",
                regex=re.compile(
                    r"(?P<a>\S+)\s+itaḥ\s+(?P<b>\S+)\s+paryantayogaḥ", re.IGNORECASE
                ),
                bytecode_fn=self._bc_range_sum,
                description="Range sum (पर्यन्तयोगः) — a itaḥ b paryantayogaḥ",
            ),
            # लोड $reg सह $val → MOVI R_reg, val
            SanskritPattern(
                name="load",
                devanagari="लोड $reg सह $val",
                iast_template="load {reg} saha {val}",
                regex=re.compile(
                    r"load\s+(?P<reg>R\d+)\s+saha\s+(?P<val>-?\d+)", re.IGNORECASE
                ),
                bytecode_fn=self._bc_load,
                description="Load value into register — load Rn saha val",
            ),
            # दर्शय $reg → PRINT R_reg
            SanskritPattern(
                name="print",
                devanagari="दर्शय $reg",
                iast_template="darśaya {reg}",
                regex=re.compile(
                    r"darśaya\s+(?P<reg>R\d+)", re.IGNORECASE
                ),
                bytecode_fn=self._bc_print,
                description="Print register — darśaya Rn",
            ),
            # $a तुल्य $b → CMP a, b
            SanskritPattern(
                name="compare",
                devanagari="$a तुल्य $b",
                iast_template="{a} tulya {b}",
                regex=re.compile(
                    r"(?P<a>\S+)\s+tulya\s+(?P<b>\S+)", re.IGNORECASE
                ),
                bytecode_fn=self._bc_cmp,
                description="Compare (तुलना) — a tulya b",
            ),
            # विराम → HALT
            SanskritPattern(
                name="halt",
                devanagari="विराम",
                iast_template="virāma",
                regex=re.compile(r"virāma", re.IGNORECASE),
                bytecode_fn=lambda m: bytearray([Op.HALT]),
                description="Halt execution (विराम)",
            ),
            # प्लुत $a → INC Ra (increment)
            SanskritPattern(
                name="increment",
                devanagari="प्लुत $a",
                iast_template="pluta {a}",
                regex=re.compile(r"pluta\s+(?P<a>R\d+)", re.IGNORECASE),
                bytecode_fn=self._bc_inc,
                description="Increment (वृद्धिः) — pluta Rn",
            ),
            # ह्रास $a → DEC Ra (decrement)
            SanskritPattern(
                name="decrement",
                devanagari="ह्रास $a",
                iast_template="hrāsa {a}",
                regex=re.compile(r"hrāsa\s+(?P<a>R\d+)", re.IGNORECASE),
                bytecode_fn=self._bc_dec,
                description="Decrement (ह्रासः) — hrāsa Rn",
            ),
            # जुष $reg → PUSH Rn
            SanskritPattern(
                name="push",
                devanagari="जुष $reg",
                iast_template="juṣa {reg}",
                regex=re.compile(r"juṣa\s+(?P<reg>R\d+)", re.IGNORECASE),
                bytecode_fn=self._bc_push,
                description="Push to stack (स्तरणम्) — juṣa Rn",
            ),
            # गृह्ण $reg → POP Rn
            SanskritPattern(
                name="pop",
                devanagari="गृह्ण $reg",
                iast_template="gṛhṇa {reg}",
                regex=re.compile(r"gṛhṇa\s+(?P<reg>R\d+)", re.IGNORECASE),
                bytecode_fn=self._bc_pop,
                description="Pop from stack (स्तरोत्तारणम्) — gṛhṇa Rn",
            ),
            # संन्धि resolve → sandhi splitting
            SanskritPattern(
                name="sandhi_split",
                devanagari="संन्धि $compound",
                iast_template="saṃdhi {compound}",
                regex=re.compile(r"saṃdhi\s+(?P<compound>\S+)", re.IGNORECASE),
                bytecode_fn=self._bc_sandhi,
                description="Sandhi resolution (सन्धिविच्छेदः) — saṃdhi compound",
            ),
            # विभक्ति $word → detect vibhakti
            SanskritPattern(
                name="vibhakti_detect",
                devanagari="विभक्ति $word",
                iast_template="vibhakti {word}",
                regex=re.compile(r"vibhakti\s+(?P<word>\S+)", re.IGNORECASE),
                bytecode_fn=self._bc_vibhakti,
                description="Vibhakti detection (विभक्तिपरीक्षा) — vibhakti word",
            ),
        ]

    # ---- Bytecode generators ----

    @staticmethod
    def _parse_reg(token: str) -> int:
        """Parse a register token like 'R0', 'R5' into an integer."""
        token = token.strip()
        if token.startswith("R") or token.startswith("r"):
            try:
                return int(token[1:])
            except ValueError:
                pass
        # Try as a symbol lookup — will be handled by caller
        return -1

    @staticmethod
    def _parse_value(token: str) -> int:
        """Parse a numeric value."""
        token = token.strip()
        try:
            return int(token)
        except ValueError:
            try:
                return int(float(token))
            except ValueError:
                return 0

    def _bc_add(self, match: re.Match) -> bytearray:
        a, b = match.group("a"), match.group("b")
        ra = self._parse_reg(a)
        rb = self._parse_reg(b)
        if ra < 0 or rb < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.IADD, 0, ra, rb])

    def _bc_mul(self, match: re.Match) -> bytearray:
        a, b = match.group("a"), match.group("b")
        ra = self._parse_reg(a)
        rb = self._parse_reg(b)
        if ra < 0 or rb < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.IMUL, 0, ra, rb])

    def _bc_sub(self, match: re.Match) -> bytearray:
        a, b = match.group("a"), match.group("b")
        ra = self._parse_reg(a)
        rb = self._parse_reg(b)
        if ra < 0 or rb < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.ISUB, 0, ra, rb])

    def _bc_div(self, match: re.Match) -> bytearray:
        a, b = match.group("a"), match.group("b")
        ra = self._parse_reg(a)
        rb = self._parse_reg(b)
        if ra < 0 or rb < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.IDIV, 0, ra, rb])

    def _bc_range_sum(self, match: re.Match) -> bytearray:
        """Compile a range sum: sum from a to b."""
        a, b = match.group("a"), match.group("b")
        ra = self._parse_reg(a)
        rb = self._parse_reg(b)
        if ra < 0 or rb < 0:
            return bytearray([Op.NOP])
        # Load values into temp registers, compute sum via loop
        # For simplicity with our bytecode, we emit a direct computation:
        # MOVI R1, (val_a); MOVI R2, (val_b); then compute sum
        # Actually we need to read current register values for range sum
        bc = bytearray()
        # MOV R1, Ra; MOV R2, Rb; then sum R0 = sum(R1..R2)
        bc.extend([Op.MOV, 1, ra])
        bc.extend([Op.MOV, 2, rb])
        # Simple: R0 = R2*(R2+1)/2 - (R1-1)*R1/2  (Gauss formula)
        # Store R1-1 in R3
        bc.extend([Op.MOV, 3, 1])
        bc.extend([Op.DEC, 3])
        # R4 = R2 * (R2 + 1)
        bc.extend([Op.MOV, 4, 2])
        bc.extend([Op.INC, 4])
        bc.extend([Op.IMUL, 5, 2, 4])
        # R4 = R5 / 2
        bc.extend([Op.MOVI, 6, 2, 0])
        bc.extend([Op.IDIV, 4, 5, 6])
        # R5 = R3 * (R3 + 1)
        bc.extend([Op.MOV, 5, 3])
        bc.extend([Op.INC, 5])
        bc.extend([Op.IMUL, 7, 3, 5])
        # R6 already = 2 from above
        bc.extend([Op.IDIV, 5, 7, 6])
        # R0 = R4 - R5
        bc.extend([Op.ISUB, 0, 4, 5])
        return bc

    def _bc_load(self, match: re.Match) -> bytearray:
        reg = match.group("reg")
        val = self._parse_value(match.group("val"))
        r = self._parse_reg(reg)
        if r < 0:
            return bytearray([Op.NOP])
        bc = bytearray([Op.MOVI, r])
        # Encode signed 16-bit immediate
        imm = val & 0xFFFF
        bc.append(imm & 0xFF)
        bc.append((imm >> 8) & 0xFF)
        return bc

    def _bc_print(self, match: re.Match) -> bytearray:
        reg = match.group("reg")
        r = self._parse_reg(reg)
        if r < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.PRINT, r])

    def _bc_cmp(self, match: re.Match) -> bytearray:
        a, b = match.group("a"), match.group("b")
        ra = self._parse_reg(a)
        rb = self._parse_reg(b)
        if ra < 0 or rb < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.ICMP, ra, rb])

    def _bc_inc(self, match: re.Match) -> bytearray:
        a = match.group("a")
        ra = self._parse_reg(a)
        if ra < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.INC, ra])

    def _bc_dec(self, match: re.Match) -> bytearray:
        a = match.group("a")
        ra = self._parse_reg(a)
        if ra < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.DEC, ra])

    def _bc_push(self, match: re.Match) -> bytearray:
        reg = match.group("reg")
        r = self._parse_reg(reg)
        if r < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.PUSH, r])

    def _bc_pop(self, match: re.Match) -> bytearray:
        reg = match.group("reg")
        r = self._parse_reg(reg)
        if r < 0:
            return bytearray([Op.NOP])
        return bytearray([Op.POP, r])

    def _bc_sandhi(self, match: re.Match) -> bytearray:
        """Resolve sandhi and display components."""
        compound = match.group("compound")
        parts = SamasaParser.split_sandhi_simple(compound)
        self._sandhi_result = parts
        return bytearray([Op.NOP])  # Metadata operation, no bytecode change

    def _bc_vibhakti(self, match: re.Match) -> bytearray:
        """Detect vibhakti of a word and display."""
        word = match.group("word")
        vb = VibhaktiValidator.detect_vibhakti(word)
        self._vibhakti_result = vb
        return bytearray([Op.NOP])  # Metadata operation

    # ---- Execution ----

    def execute_line(self, line: str) -> ExecutionResult:
        """
        Parse and execute a single Sanskrit NL line.
        Returns the execution result.
        """
        self._print_output = None
        self._sandhi_result = None
        self._vibhakti_result = None
        line = line.strip()

        if not line or line.startswith("#"):
            return ExecutionResult(success=True, trace=self.vm.trace_log)

        # Check lakāra markers
        self._check_lakara(line)

        # Reset VM for fresh execution if HALT was issued
        if self.vm.halted:
            self.vm = FluxVM(trace=self.trace)

        # Try each pattern
        for pattern in self._patterns:
            match = pattern.regex.search(line)
            if match:
                bytecode = pattern.bytecode_fn(match)
                self._history.append(line)
                # Set bytecode and execute
                self.vm.bytecode = bytecode
                self.vm.pc = 0
                self.vm.halted = False
                self.vm.error = None
                result = self.vm.execute()
                # Capture print output
                self._print_output = getattr(self.vm, '_print_output', None)
                result.trace = self.vm.trace_log
                return result

        return ExecutionResult(
            success=False,
            error=f"अज्ञातं वाक्यम् (unrecognized pattern): {line}",
            trace=self.vm.trace_log,
        )

    def execute_lines(self, lines: str) -> list[ExecutionResult]:
        """Execute multiple lines, returning results for each."""
        results = []
        for line in lines.strip().split("\n"):
            line = line.strip()
            if line:
                results.append(self.execute_line(line))
        return results

    def execute_program(self, program: str) -> ExecutionResult:
        """
        Execute a multi-line program as a single bytecode sequence.
        All lines are compiled into one bytecode array, then executed together.
        """
        self.vm = FluxVM(trace=self.trace)
        combined = bytearray()

        for line in program.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            for pattern in self._patterns:
                match = pattern.regex.search(line)
                if match:
                    bc = pattern.bytecode_fn(match)
                    combined.extend(bc)
                    self._history.append(line)
                    break

        self.vm.bytecode = combined
        self.vm.pc = 0
        return self.vm.execute()

    def reset(self) -> None:
        """Reset the VM to initial state."""
        self.vm = FluxVM(trace=self.trace)
        self._history.clear()
        self._symbols.clear()
        self.lakara_context = LakaraDetector.make_context(self.default_lakara)

    def set_register(self, reg: int, value: int) -> None:
        """Directly set a register value (utility method)."""
        self.vm.write_reg(reg, value)

    def _check_lakara(self, line: str) -> None:
        """Check for lakāra markers in the input line and update context."""
        markers = {
            "kṛ": Lakara.LAT, "akṛ": Lakara.LAN, "cakṛ": Lakara.LIT,
            "bhava": Lakara.ASIRLING, "kuryāt": Lakara.VIDHILING,
        }
        for marker, lakara in markers.items():
            if marker in line:
                self.lakara_context = LakaraDetector.make_context(lakara)
                break

    def sandhi_result(self) -> list[str] | None:
        """Return the result of the last sandhi split operation."""
        return getattr(self, '_sandhi_result', None)

    def vibhakti_result(self) -> Vibhakti | None:
        """Return the result of the last vibhakti detection."""
        return getattr(self, '_vibhakti_result', None)

    # ---- Dual number (dvivacana) support ----

    @staticmethod
    def pairwise_op(values: list[int], op: str) -> list[int]:
        """
        Apply an operation pairwise (dvivacana / dual number).
        Returns a list of (n-1) results for n input values.
        """
        results = []
        for i in range(len(values) - 1):
            a, b = values[i], values[i + 1]
            match op:
                case "add":
                    results.append(a + b)
                case "sub":
                    results.append(a - b)
                case "mul":
                    results.append(a * b)
                case "div":
                    results.append(a // b if b != 0 else 0)
                case "mod":
                    results.append(a % b if b != 0 else 0)
                case _:
                    results.append(0)
        return results

    # ---- Quick execution helpers ----

    def quick_exec(self, program: str) -> ExecutionResult:
        """Compile and execute a multi-line program, return final result."""
        return self.execute_program(program)

    def eval_math(self, expr: str) -> int:
        """
        Evaluate a mathematical expression in Sanskrit.
        Returns the integer result from R0.
        """
        result = self.execute_line(expr)
        return result.result if result.success else 0


# ---------------------------------------------------------------------------
# Sanskrit number words → integers
# ---------------------------------------------------------------------------

SANSKRIT_NUMBERS: dict[str, int] = {
    "śūnya": 0,  "pūrṇa": 0,       # शून्य / पूर्ण
    "eka": 1,    "ekam": 1,          # एक / एकम्
    "dvi": 2,    "dvau": 2,          # द्वि / द्वौ
    "tri": 3,    "trīṇi": 3,        # त्रि / त्रीणि
    "catur": 4,  "catvāri": 4,      # चतुर् / चत्वारि
    "pañcan": 5, "pañca": 5,        # पञ्चन् / पञ्च
    "ṣaḍ": 6,   "ṣaṭ": 6,         # षड् / षट्
    "sapta": 7,                     # सप्त
    "aṣṭa": 8,                     # अष्ट
    "nava": 9,                      # नव
    "daśa": 10,                     # दश
    "vimśati": 20,                  # विंशति
    "triṃśat": 30,                  # त्रिंशत्
    "catvāriṃśat": 40,             # चत्वारिंशत्
    "pañcāśat": 50,                # पञ्चाशत्
    "ṣaṣṭi": 60,                  # षष्टि
    "saptati": 70,                  # सप्तति
    "aśīti": 80,                   # अशीति
    "navati": 90,                  # नवति
    "śata": 100,                   # शत
    "sahasra": 1000,               # सहस्र
    "ayuta": 10000,                # अयुत
    "lakṣa": 100000,              # लक्ष
    "koṭi": 10000000,             # कोटि
}


def sanskrit_num_to_int(word: str) -> int | None:
    """Convert a Sanskrit number word to its integer value."""
    return SANSKRIT_NUMBERS.get(word.lower())
