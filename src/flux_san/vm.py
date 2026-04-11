"""
FluxVMSan — Vibhakti-Scoped 64-Register Virtual Machine
=========================================================

A fully-sandboxed FLUX VM where every register access is governed by the
aṣṭau-vibhakti (8-case) scope system.  Registers carry scope metadata
so the VM can enforce Pāṇinian access rules at the bytecode level.

Architecture:
  - 64 general-purpose registers (R0–R63), each with a vibhakti scope tag
  - 256-byte call stack, 256-byte data stack
  - Zero-flag, Negative-flag, Carry-flag (ZF / NF / CF)
  - Per-instruction lakāra (execution mode) gating
  - A2A protocol registers (TELL / ASK / DELEGATE / BROADCAST / TRUST_CHECK / CAP_REQUIRE)
  - Devanāgarī register aliases via the Sanskrit counting system

Vibhakti → Scope Mapping:
  ┌─────────────────┬────────────────────────┬───────────────────────────────────┐
  │ Case (vibhakti) │ Scope                  │ Effect on register access        │
  ├─────────────────┼────────────────────────┼───────────────────────────────────┤
  │ 1. prathama     │ PUBLIC                 │ Any agent may read               │
  │ 2. dvitiya      │ OBJECT                 │ Argument passing, receives action│
  │ 3. tritiya      │ FUNCTION               │ Called as instrument / tool      │
  │ 4. chaturthi    │ CAPABILITY             │ Permission grant / receive       │
  │ 5. panchami     │ ORIGIN                 │ Export / source scope            │
  │ 6. shashthi     │ OWNERSHIP              │ Owner-only read/write            │
  │ 7. saptami      │ CONTEXT                │ Region-local access              │
  │ 8. sambodhana   │ INVOCATION             │ A2A agent-to-agent call          │
  └─────────────────┴────────────────────────┴───────────────────────────────────┘

From Pāṇini's Aṣṭādhyāyī:
  vibhaktayaḥ aṣṭau — "The cases are eight" (1.1.1 / vibhakti-sūtra)
"""

from __future__ import annotations

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Callable, Any

from flux_san.vibhakti import (
    Vibhakti,
    ScopeLevel,
    ScopedAccess,
    VibhaktiValidator,
)
from flux_san.lakara import (
    Lakara,
    ExecutionMode,
    LakaraContext,
    LakaraDetector,
)


# ---------------------------------------------------------------------------
# FLUX Bytecode Opcodes — complete instruction set
# ---------------------------------------------------------------------------

class Opcode(IntEnum):
    """FLUX-san bytecode opcodes — variable-length encoding.

    Layout mirrors the TypeScript flux/lib/flux/vm.ts ISA with additions
    for the Sanskrit-native A2A protocol layer.
    """
    # --- Control flow (नियन्त्रणप्रवाहः) ---
    NOP          = 0x00  # No operation — √as (to be) inaction
    MOV          = 0x01  # Copy register → register
    LOAD         = 0x02  # Load from memory/register
    STORE        = 0x03  # Store to memory/register
    JMP          = 0x04  # Unconditional jump — √gam (to go)
    JZ           = 0x05  # Jump if zero
    JNZ          = 0x06  # Jump if not zero
    CALL         = 0x07  # Call subroutine — √kṛ (to do)

    # --- Arithmetic (गणितम्) ---
    IADD         = 0x08  # Integer add — √yuj (to join)
    ISUB         = 0x09  # Integer subtract
    IMUL         = 0x0A  # Integer multiply — √guṇ (to multiply)
    IDIV         = 0x0B  # Integer divide — √bhāj (to divide)
    IMOD         = 0x0C  # Integer modulo — śeṣa (remainder)
    INEG         = 0x0D  # Integer negate — viparyaya
    INC          = 0x0E  # Increment — pluta (increase)
    DEC          = 0x0F  # Decrement — hrāsa (decrease)

    # --- Bitwise (खण्डक्रियाः) ---
    IAND         = 0x10
    IOR          = 0x11
    IXOR         = 0x12
    INOT         = 0x13

    # --- Comparison (तुलना) ---
    ICMP         = 0x18  # Integer compare — tulya
    IEQ          = 0x19  # Is equal
    ILT          = 0x1A  # Is less than
    ILE          = 0x1B  # Is less-or-equal
    IGT          = 0x1C  # Is greater than
    IGE          = 0x1D  # Is greater-or-equal
    TEST         = 0x1E  # Test register value

    # --- Stack (स्तरक्रियाः) ---
    PUSH         = 0x20  # Push onto stack
    POP          = 0x21  # Pop from stack
    DUP          = 0x22  # Duplicate top of stack
    SWAP         = 0x23  # Swap top two stack elements
    ROT          = 0x24  # Rotate top three stack elements

    # --- Subroutines (उपक्रमः) ---
    RET          = 0x28  # Return from call
    CALL_IND     = 0x29  # Indirect call via register

    # --- Immediate (तत्कालम्) ---
    MOVI         = 0x2B  # Move immediate (signed 16-bit)

    # --- Flags-based branch (ध्वज-शाखा) ---
    CMP          = 0x2D  # Compare (sets flags)
    JE           = 0x2E  # Jump if equal (ZF=1)
    JNE          = 0x2F  # Jump if not equal (ZF=0)

    # --- Floating-point (दशमांशगणितम्) ---
    FADD         = 0x40
    FSUB         = 0x41
    FMUL         = 0x42
    FDIV         = 0x43

    # --- A2A Agent Protocol (अजेन्त-प्रोटोकॉल्) ---
    TELL         = 0x60  # One-way message — √brū / बृ (to speak)
    ASK          = 0x61  # Question / request — √pṛcch (to ask)
    DELEGATE     = 0x62  # Transfer task — √niyuj (to assign)
    BROADCAST    = 0x63  # Announce to all — √prakaraṇ (to proclaim)
    TRUST_CHECK  = 0x64  # Verify trust — √adhi-īś (to rule over)
    CAP_REQUIRE  = 0x65  # Require capability — √śakti (power/capability)

    # --- I/O (आगत-निर्गतम्) ---
    PRINT        = 0xFE  # Print register value — darśaya
    HALT         = 0xFF  # Halt execution — virāma / √sthā (to stand firm)


# Opcode name table for disassembly
OPCODE_NAMES: dict[int, str] = {op.value: op.name for op in Opcode}


# ---------------------------------------------------------------------------
# Devanāgarī register names — Sanskrit number system
# ---------------------------------------------------------------------------

# Registers 0–7 have special names from Sanskrit grammatical tradition
# Registers 8–63 use Sanskrit cardinal numbers
_DEVANAGARI_REG_SPECIAL: dict[int, str] = {
    0: "शून्यम्",     # śūnyam — zero / accumulator
    1: "एकम्",       # ekam — one / base
    2: "द्वितीयम्",   # dvitīyam — second
    3: "तृतीयम्",     # tṛtīyam — third
    4: "चतुर्थम्",    # caturtham — fourth
    5: "पञ्चमम्",     # pañcamam — fifth
    6: "षष्ठम्",      # ṣaṣṭham — sixth
    7: "सप्तमम्",     # saptamam — seventh
}

_SANSKRIT_CARDINALS: list[str] = [
    "śūnyam", "ekam", "dvitiyam", "tṛtīyam", "caturtham",
    "pañcamam", "ṣaṣṭham", "saptamam", "aṣṭamam", "navamam",
    "daśamam", "ekādaśam", "dvādaśam", "trayodaśam", "caturdaśam",
    "pañcadaśam", "ṣoḍaśam", "saptadaśam", "aṣṭādaśam", "navadaśam",
    "viṃśatitamaḥ",  # 20th
]


def register_devanagari(n: int) -> str:
    """Return the Devanāgarī name for register *n*.

    Registers 0–7 use grammatical ordinal names (prathamā, dvitīyā, …).
    Registers 8–63 use the Sanskrit cardinal system.
    """
    if 0 <= n < 8:
        return _DEVANAGARI_REG_SPECIAL[n]
    if n < len(_SANSKRIT_CARDINALS):
        return _SANSKRIT_CARDINALS[n]
    # For higher registers, compose from tens + units
    if n < 64:
        return f"R{n}_({n + 1}म्)"
    return f"R{n}"


def register_name(n: int) -> str:
    """Return the IAST name for register *n*."""
    if 0 <= n < 8:
        return _DEVANAGARI_REG_SPECIAL[n].replace("म्", "").replace("ः", "")
    return f"R{n}"


# ---------------------------------------------------------------------------
# Vibhakti-scoped register descriptor
# ---------------------------------------------------------------------------

@dataclass
class ScopedRegister:
    """A register tagged with a vibhakti scope level.

    The VM checks this tag on every access to enforce Pāṇinian scope rules:
      - prathama (nominative)  → public read — any context may read
      - dvitiya  (accusative)  → argument passing — receives data
      - tritiya  (instrumental) → function calls — acts as tool
      - chaturthi (dative)     → capability grant — receives permissions
      - panchami (ablative)    → export/source — provides data outward
      - shashthi (genitive)    → ownership — read/write only by owner
      - saptami  (locative)    → context/region — within-region access
      - sambodhana (vocative)  → A2A invocation — agent-to-agent call
    """
    index: int
    value: int = 0
    scope: Vibhakti = Vibhakti.PRATHAMA
    owner: str = ""              # Agent id that owns this register
    region: int = 0              # Region id for saptami (locative) scope

    @property
    def scope_level(self) -> ScopeLevel:
        return self.scope.scope

    def __repr__(self) -> str:
        return (
            f"ScopedRegister(R{self.index}/{register_devanagari(self.index)}, "
            f"value={self.value}, scope={self.scope.devanagari}, "
            f"owner={self.owner!r}, region={self.region})"
        )


# ---------------------------------------------------------------------------
# Scope violation exception
# ---------------------------------------------------------------------------

class VibhaktiScopeError(Exception):
    """Raised when a register access violates vibhakti scope rules.

    For example, attempting to write to a shashthi (genitive / ownership)
    register from a non-owner agent, or reading a saptami (locative)
    register from outside its region.
    """

    def __init__(self, register: int, attempted_scope: Vibhakti,
                 required_scope: Vibhakti | None, message: str = ""):
        self.register = register
        self.attempted_scope = attempted_scope
        self.required_scope = required_scope
        super().__init__(
            message or (
                f"Vibhakti scope violation: R{register} "
                f"(requires {required_scope.devanagari if required_scope else 'any'}) "
                f"accessed from {attempted_scope.devanagari} scope"
            )
        )


# ---------------------------------------------------------------------------
# Instruction — decoded bytecode instruction
# ---------------------------------------------------------------------------

@dataclass
class Instruction:
    """A decoded bytecode instruction with operands."""
    opcode: Opcode
    operands: list[int] = field(default_factory=list)
    address: int = 0  # PC where this instruction starts

    @property
    def mnemonic(self) -> str:
        return self.opcode.name

    def disassemble(self) -> str:
        """Return human-readable disassembly with Devanāgarī register names."""
        ops = ", ".join(
            register_devanagari(o) if 0 <= o < 64 else str(o)
            for o in self.operands
        )
        return f"  {self.address:04x}: {self.mnemonic:<12s} {ops}"


# ---------------------------------------------------------------------------
# VM execution event (for tracing / debugging)
# ---------------------------------------------------------------------------

@dataclass
class VMEvent:
    """Trace event emitted during execution."""
    cycle: int
    pc: int
    opcode: Opcode
    operands: list[int]
    registers_snapshot: dict[int, int] = field(default_factory=dict)
    flags_zero: bool = False
    flags_negative: bool = False
    stack_depth: int = 0
    scope_context: Vibhakti | None = None
    note: str = ""

    def __repr__(self) -> str:
        return (
            f"VMEvent(cycle={self.cycle}, pc=0x{self.pc:04x}, "
            f"{self.opcode.name}, note={self.note!r})"
        )


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------

@dataclass
class VMResult:
    """Result of a VM execution run."""
    success: bool
    result: int = 0                    # Final value of R0
    registers: list[int] = field(default_factory=lambda: [0] * 64)
    cycles: int = 0
    error: str | None = None
    halted: bool = False
    trace: list[str] = field(default_factory=list)
    events: list[VMEvent] = field(default_factory=list)
    scope_violations: list[VibhaktiScopeError] = field(default_factory=list)
    a2a_messages: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Capabilities — for CHATURTHI (dative) scope enforcement
# ---------------------------------------------------------------------------

@dataclass
class Capability:
    """A capability grant tracked by the VM for chaturthi-scope checks."""
    agent_id: str
    permission: str          # e.g., "read", "write", "execute", "delegate"
    target_register: int
    granted_by: str = ""


# ---------------------------------------------------------------------------
# FluxVMSan — the main VM
# ---------------------------------------------------------------------------

class FluxVMSan:
    """Vibhakti-scoped 64-register FLUX Virtual Machine.

    Every register access is validated against the register's vibhakti
    scope tag.  The VM also supports:
      - Lakāra-gated execution (deferred, forced, speculative, etc.)
      - A2A protocol instructions (TELL, ASK, DELEGATE, BROADCAST)
      - Trust checks and capability requirements
      - Full trace/debug support

    Usage::

        vm = FluxVMSan()
        vm.set_register(1, 42, scope=Vibhakti.PRATHAMA)
        vm.set_register(2, 7, scope=Vibhakti.PRATHAMA)
        vm.load_bytecode([
            Opcode.IADD, 0, 1, 2,
            Opcode.PRINT, 0,
            Opcode.HALT,
        ])
        result = vm.execute()
        assert result.result == 49
    """

    NUM_REGISTERS: int = 64
    MAX_STACK: int = 256
    DEFAULT_MAX_CYCLES: int = 1_000_000

    def __init__(
        self,
        trace: bool = False,
        max_cycles: int = DEFAULT_MAX_CYCLES,
        current_agent: str = "main",
        current_region: int = 0,
        enforce_scope: bool = True,
    ):
        # Registers — each with vibhakti scope
        self._registers: list[ScopedRegister] = [
            ScopedRegister(index=i) for i in range(self.NUM_REGISTERS)
        ]

        # Stacks
        self._call_stack: list[int] = []
        self._data_stack: list[int] = []

        # Flags
        self._flag_zero: bool = False
        self._flag_negative: bool = False
        self._flag_carry: bool = False

        # Program counter
        self._pc: int = 0
        self._halted: bool = False
        self._cycles: int = 0
        self._error: str | None = None

        # Bytecode buffer
        self._bytecode: bytearray = bytearray()

        # Execution context
        self._current_agent: str = current_agent
        self._current_region: int = current_region
        self._enforce_scope: bool = enforce_scope
        self._current_lakara: Lakara = Lakara.LAT
        self._lakara_context: LakaraContext = LakaraDetector.make_context(Lakara.LAT)

        # Tracing
        self._trace: bool = trace
        self._trace_log: list[str] = []
        self._events: list[VMEvent] = []
        self._scope_violations: list[VibhaktiScopeError] = []

        # A2A message log
        self._a2a_messages: list[dict[str, Any]] = []

        # Capability registry (for chaturthi-scope enforcement)
        self._capabilities: list[Capability] = []

        # Trust registry (for sambodhana-scope A2A enforcement)
        self._trust_store: dict[str, set[str]] = {}  # agent → trusted_agents

        # Region registry (for saptami-scope enforcement)
        self._region_members: dict[int, set[str]] = {}  # region → agents

        # Callback hooks (for extending the VM)
        self._hooks: dict[Opcode, list[Callable]] = {
            op: [] for op in Opcode
        }
        self._print_output: int | None = None

    # ---- Register access with vibhakti scope enforcement ----

    def read_reg(self, r: int, accessing_scope: Vibhakti | None = None) -> int:
        """Read register *r* with vibhakti scope checking.

        If the register's scope is more restrictive than the accessor's
        scope, a VibhaktiScopeError is raised (or logged if enforcement
        is lenient).

        Args:
            r: Register index (0–63).
            accessing_scope: The vibhakti from which the read originates.
                Defaults to prathama (public / most permissive).
        """
        if not (0 <= r < self.NUM_REGISTERS):
            return 0

        reg = self._registers[r]

        if self._enforce_scope and reg.scope != Vibhakti.PRATHAMA:
            self._check_scope_read(r, reg, accessing_scope or Vibhakti.PRATHAMA)

        return reg.value

    def write_reg(
        self,
        r: int,
        value: int,
        scope: Vibhakti | None = None,
        accessing_scope: Vibhakti | None = None,
    ) -> None:
        """Write *value* to register *r* with vibhakti scope checking.

        Args:
            r: Register index (0–63).
            value: Integer value to store.
            scope: Override the register's scope tag after write.
            accessing_scope: The vibhakti from which the write originates.
        """
        if not (0 <= r < self.NUM_REGISTERS):
            return

        reg = self._registers[r]

        if self._enforce_scope and reg.scope != Vibhakti.PRATHAMA:
            self._check_scope_write(r, reg, accessing_scope or Vibhakti.PRATHAMA)

        reg.value = value
        if scope is not None:
            reg.scope = scope

    def set_register(
        self,
        r: int,
        value: int,
        scope: Vibhakti = Vibhakti.PRATHAMA,
        owner: str = "",
        region: int = 0,
    ) -> None:
        """Directly set a register's value and scope metadata.

        This bypasses scope enforcement (it's used to *establish* scope,
        not to check it).
        """
        if 0 <= r < self.NUM_REGISTERS:
            self._registers[r].value = value
            self._registers[r].scope = scope
            self._registers[r].owner = owner or self._current_agent
            self._registers[r].region = region or self._current_region

    def get_register(self, r: int) -> ScopedRegister | None:
        """Return the ScopedRegister object for register *r*, or None."""
        if 0 <= r < self.NUM_REGISTERS:
            return self._registers[r]
        return None

    def get_register_value(self, r: int) -> int:
        """Get register value without scope check (direct read)."""
        if 0 <= r < self.NUM_REGISTERS:
            return self._registers[r].value
        return 0

    @property
    def registers(self) -> list[int]:
        """Return a flat list of all register values."""
        return [r.value for r in self._registers]

    # ---- Scope enforcement ----

    def _check_scope_read(
        self, r: int, reg: ScopedRegister, accessing: Vibhakti
    ) -> None:
        """Validate that a read access is permitted by vibhakti rules.

        Read rules by register scope:
          - PRATHAMA (public):   Any agent may read.
          - DVITIYA (object):    Any agent may read (data is being passed).
          - TRITIYA (function):  Only function callers may read.
          - CHATURTHI (capability): Only agents with the capability may read.
          - PANCHAMI (origin):   Any agent may read (export/source).
          - SHASHTHI (ownership): Only the owner agent may read.
          - SAPTAMI (locative):  Only agents in the same region may read.
          - SAMBODHANA (invocation): Only trusted agents may read.
        """
        match reg.scope:
            case Vibhakti.PRATHAMA | Vibhakti.DVITIYA | Vibhakti.PANCHAMI:
                # Public, argument, and origin scopes allow any read
                pass

            case Vibhakti.TRITIYA:
                # Instrumental — only callable contexts
                if accessing not in (Vibhakti.TRITIYA, Vibhakti.PRATHAMA):
                    self._log_violation(
                        r, accessing, reg.scope,
                        "trītīyā (instrumental) register requires "
                        "function-call scope for reading"
                    )

            case Vibhakti.CHATURTHI:
                # Dative — only agents with the capability
                if not self._has_capability(self._current_agent, "read", r):
                    self._log_violation(
                        r, accessing, reg.scope,
                        "caturthī (dative) register requires capability grant"
                    )

            case Vibhakti.SHASHTHI:
                # Genitive — owner-only
                if reg.owner and reg.owner != self._current_agent:
                    self._log_violation(
                        r, accessing, reg.scope,
                        f"ṣaṣṭhī (genitive) register owned by {reg.owner!r}, "
                        f"not {self._current_agent!r}"
                    )

            case Vibhakti.SAPTAMI:
                # Locative — region-local
                if reg.region != self._current_region:
                    self._log_violation(
                        r, accessing, reg.scope,
                        f"saptamī (locative) register in region {reg.region}, "
                        f"current region is {self._current_region}"
                    )

            case Vibhakti.SAMBODHANA:
                # Vocative — A2A trusted agents only
                if not self._is_trusted(self._current_agent, reg.owner):
                    self._log_violation(
                        r, accessing, reg.scope,
                        f"sambodhana (vocative) register requires trust for A2A"
                    )

    def _check_scope_write(
        self, r: int, reg: ScopedRegister, accessing: Vibhakti
    ) -> None:
        """Validate that a write access is permitted by vibhakti rules.

        Write rules are stricter than read rules:
          - PRATHAMA (public):   Any agent may write.
          - DVITIYA (object):    Only the action's target may write.
          - TRITIYA (function):  Only the called function may write back results.
          - CHATURTHI (capability): Only with explicit capability.
          - PANCHAMI (origin):   Only the source/owner may write.
          - SHASHTHI (ownership): Owner-only write.
          - SAPTAMI (locative):  Region-local write only.
          - SAMBODHANA (invocation): Only the invoked agent may write.
        """
        match reg.scope:
            case Vibhakti.PRATHAMA:
                # Public — any write allowed
                pass

            case Vibhakti.DVITIYA:
                # Accusative — only the direct object / recipient may write
                if accessing != Vibhakti.DVITIYA and accessing != Vibhakti.PRATHAMA:
                    self._log_violation(
                        r, accessing, reg.scope,
                        "dvitīyā (accusative) register requires object scope for writing"
                    )

            case Vibhakti.TRITIYA:
                if accessing != Vibhakti.TRITIYA:
                    self._log_violation(
                        r, accessing, reg.scope,
                        "tṛtīyā (instrumental) register requires function scope for writing"
                    )

            case Vibhakti.CHATURTHI:
                if not self._has_capability(self._current_agent, "write", r):
                    self._log_violation(
                        r, accessing, reg.scope,
                        "caturthī (dative) register requires capability for writing"
                    )

            case Vibhakti.PANCHAMI:
                if reg.owner and reg.owner != self._current_agent:
                    self._log_violation(
                        r, accessing, reg.scope,
                        "pañcamī (ablative) register requires origin-owner for writing"
                    )

            case Vibhakti.SHASHTHI:
                if reg.owner and reg.owner != self._current_agent:
                    self._log_violation(
                        r, accessing, reg.scope,
                        f"ṣaṣṭhī (genitive) register owned by {reg.owner!r}"
                    )

            case Vibhakti.SAPTAMI:
                if reg.region != self._current_region:
                    self._log_violation(
                        r, accessing, reg.scope,
                        f"saptamī (locative) register in region {reg.region}"
                    )

            case Vibhakti.SAMBODHANA:
                if not self._is_trusted(self._current_agent, reg.owner):
                    self._log_violation(
                        r, accessing, reg.scope,
                        "sambodhana (vocative) register requires trust for A2A write"
                    )

    def _log_violation(
        self,
        register: int,
        accessing: Vibhakti,
        required: Vibhakti,
        message: str,
    ) -> None:
        """Record a scope violation."""
        violation = VibhaktiScopeError(register, accessing, required, message)
        self._scope_violations.append(violation)
        if self._enforce_scope:
            self._error = str(violation)
            self._halted = True

    # ---- Capabilities ----

    def grant_capability(
        self, agent_id: str, permission: str, target_register: int,
        granted_by: str = "",
    ) -> None:
        """Grant a capability for chaturthi-scope access."""
        cap = Capability(
            agent_id=agent_id,
            permission=permission,
            target_register=target_register,
            granted_by=granted_by or self._current_agent,
        )
        self._capabilities.append(cap)

    def _has_capability(
        self, agent_id: str, permission: str, register: int
    ) -> bool:
        """Check if an agent holds a capability for a register."""
        for cap in self._capabilities:
            if (cap.agent_id == agent_id
                    and cap.permission == permission
                    and cap.target_register == register):
                return True
        return False

    # ---- Trust ----

    def add_trust(self, agent: str, trusted_agent: str) -> None:
        """Add a trust relationship for sambodhana-scope."""
        if agent not in self._trust_store:
            self._trust_store[agent] = set()
        self._trust_store[agent].add(trusted_agent)

    def _is_trusted(self, agent: str, by_agent: str) -> bool:
        """Check if *agent* is trusted by *by_agent*."""
        trusted = self._trust_store.get(by_agent, set())
        return agent in trusted or by_agent == "" or agent == by_agent

    # ---- Region ----

    def join_region(self, agent: str, region: int) -> None:
        """Add an agent to a region for saptami-scope."""
        if region not in self._region_members:
            self._region_members[region] = set()
        self._region_members[region].add(agent)

    # ---- Stack operations ----

    def push(self, value: int) -> None:
        """Push value onto data stack."""
        if len(self._data_stack) < self.MAX_STACK:
            self._data_stack.append(value)

    def pop(self) -> int:
        """Pop value from data stack. Returns 0 if empty."""
        return self._data_stack.pop() if self._data_stack else 0

    @property
    def stack_depth(self) -> int:
        """Current data stack depth."""
        return len(self._data_stack)

    # ---- Flags ----

    def _update_flags(self, result: int) -> None:
        """Update zero and negative flags from an arithmetic result."""
        self._flag_zero = result == 0
        self._flag_negative = result < 0

    # ---- Bytecode loading ----

    def load_bytecode(self, code: list[int] | bytearray | bytes) -> None:
        """Load bytecode into the VM."""
        self._bytecode = bytearray(code)
        self._pc = 0
        self._halted = False
        self._error = None

    def _read_byte(self) -> int:
        """Read one byte at current PC and advance."""
        val = self._bytecode[self._pc] if self._pc < len(self._bytecode) else 0
        self._pc += 1
        return val

    def _read_u16(self) -> int:
        """Read a little-endian unsigned 16-bit value at current PC."""
        lo = self._read_byte()
        hi = self._read_byte()
        return lo | (hi << 8)

    def _read_signed16(self) -> int:
        """Read a little-endian signed 16-bit value."""
        val = self._read_u16()
        return val - 65536 if val > 32767 else val

    # ---- Disassembly ----

    def disassemble(self) -> list[str]:
        """Disassemble the loaded bytecode into human-readable lines."""
        lines = []
        lines.append("╔══════════════════════════════════════════════════════╗")
        lines.append("║  FLUX-san Bytecode Disassembly                      ║")
        lines.append("║  प्रवाहिनी सङ्केतविच्छेदः                              ║")
        lines.append("╠══════════════════════════════════════════════════════╣")

        pc = 0
        bc = self._bytecode
        while pc < len(bc):
            op_val = bc[pc]
            op_name = OPCODE_NAMES.get(op_val, f"UNKNOWN(0x{op_val:02x})")
            start_pc = pc

            # Determine operand count
            op = Opcode(op_val) if op_val in OPCODE_NAMES else None
            operands: list[int] = []
            pc += 1

            if op in (
                Opcode.MOV, Opcode.LOAD, Opcode.STORE,
                Opcode.ICMP, Opcode.CMP, Opcode.CALL_IND,
                Opcode.PUSH, Opcode.POP,
            ):
                # Two register operands
                if pc < len(bc):
                    operands.append(bc[pc]); pc += 1
                if pc < len(bc):
                    operands.append(bc[pc]); pc += 1
            elif op in (
                Opcode.IADD, Opcode.ISUB, Opcode.IMUL, Opcode.IDIV, Opcode.IMOD,
            ):
                # Three register operands
                for _ in range(3):
                    if pc < len(bc):
                        operands.append(bc[pc]); pc += 1
            elif op in (Opcode.MOVI,):
                # Register + signed 16-bit immediate
                if pc < len(bc):
                    operands.append(bc[pc]); pc += 1
                if pc + 1 < len(bc):
                    operands.append(bc[pc] | (bc[pc + 1] << 8)); pc += 2
            elif op in (Opcode.JZ, Opcode.JNZ):
                # Register + address
                if pc < len(bc):
                    operands.append(bc[pc]); pc += 1
                if pc + 1 < len(bc):
                    operands.append(bc[pc] | (bc[pc + 1] << 8)); pc += 2
            elif op in (Opcode.JMP, Opcode.JE, Opcode.JNE, Opcode.CALL):
                # Address only
                if pc + 1 < len(bc):
                    operands.append(bc[pc] | (bc[pc + 1] << 8)); pc += 2
            elif op in (Opcode.PRINT, Opcode.HALT, Opcode.RET, Opcode.NOP):
                pass  # No operands (PRINT takes one operand in the old VM)

            # Format with Devanāgarī register names
            ops_str = ", ".join(
                register_devanagari(o) if 0 <= o < 64 else f"0x{o:04x}"
                for o in operands
            )
            lines.append(f"  {start_pc:04x}: {op_name:<12s} {ops_str}")

        lines.append("╚══════════════════════════════════════════════════════╝")
        return lines

    # ---- Lakara gating ----

    def set_lakara(self, lakara: Lakara) -> None:
        """Set the current lakāra (execution mode) for the VM.

        The lakāra determines how subsequent instructions are dispatched:
          - laṭ (present)     → normal sequential execution
          - laṅ (imperfect)   → conditional branch
          - liṭ (perfect)     → verified / cached execution
          - luṅ (aorist)      → immediate / atomic execution
          - lṛṭ (future)      → deferred execution
          - lṛṅ (conditional) → speculative execution
          - vidhiliṅ (potential) → speculative with rollback
          - āśīrliṅ (imperative) → forced execution
        """
        self._current_lakara = lakara
        self._lakara_context = LakaraDetector.make_context(lakara)

    def _should_execute(self) -> bool:
        """Check if the current instruction should execute under the active lakāra."""
        return self._lakara_context.should_execute

    # ---- Event tracing ----

    def _emit_event(
        self, opcode: Opcode, operands: list[int], note: str = ""
    ) -> None:
        """Emit a VM trace event."""
        if not self._trace:
            return
        event = VMEvent(
            cycle=self._cycles,
            pc=self._pc - 1,
            opcode=opcode,
            operands=list(operands),
            flags_zero=self._flag_zero,
            flags_negative=self._flag_negative,
            stack_depth=len(self._data_stack),
            note=note,
        )
        self._events.append(event)

    def _log_trace(self, message: str) -> None:
        """Add to trace log."""
        if self._trace:
            self._trace_log.append(message)

    # ---- Execution ----

    def execute(self) -> VMResult:
        """Execute loaded bytecode until HALT or error.

        Returns a VMResult with final register state, cycle count, and
        any errors or scope violations.
        """
        bc = self._bytecode
        result_registers = list(self.registers)

        while self._pc < len(bc) and not self._halted:
            if self._cycles >= self._max_cycles_internal:
                self._error = "चक्रसीमातिक्रमः — max cycles exceeded"
                break

            self._cycles += 1

            # Lakāra gate — check if this instruction should execute
            if not self._should_execute():
                # Skip the instruction without executing
                self._skip_instruction()
                continue

            op_val = bc[self._pc]
            start_pc = self._pc

            try:
                op = Opcode(op_val) if op_val in OPCODE_NAMES else None
            except ValueError:
                op = None

            if op is None:
                self._pc += 1
                continue

            self._pc += 1  # Advance past opcode byte
            operands: list[int] = []

            match op:
                case Opcode.NOP:
                    self._emit_event(op, [], "√as — no operation")

                case Opcode.MOV:
                    rd, rs = self._read_byte(), self._read_byte()
                    operands = [rd, rs]
                    val = self.read_reg(rs)
                    self.write_reg(rd, val)
                    self._emit_event(op, operands, f"R{rd} ← R{rs} ({val})")

                case Opcode.LOAD:
                    rd, rs = self._read_byte(), self._read_byte()
                    operands = [rd, rs]
                    val = self.read_reg(rs)
                    self.write_reg(rd, val)
                    self._emit_event(op, operands, f"√vid — R{rd} ← R{rs} ({val})")

                case Opcode.STORE:
                    rs, rd = self._read_byte(), self._read_byte()
                    operands = [rs, rd]
                    val = self.read_reg(rs)
                    self.write_reg(rd, val)
                    self._emit_event(op, operands, f"√dā — R{rd} ← R{rs} ({val})")

                case Opcode.MOVI:
                    r = self._read_byte()
                    imm = self._read_signed16()
                    operands = [r, imm]
                    self.write_reg(r, imm)
                    self._update_flags(imm)
                    self._emit_event(op, operands, f"R{r} ← {imm}")

                case Opcode.IADD:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    operands = [rd, ra, rb]
                    a, b = self.read_reg(ra), self.read_reg(rb)
                    result = a + b
                    self.write_reg(rd, result)
                    self._update_flags(result)
                    self._emit_event(op, operands, f"√yuj — {a} + {b} = {result}")

                case Opcode.ISUB:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    operands = [rd, ra, rb]
                    a, b = self.read_reg(ra), self.read_reg(rb)
                    result = a - b
                    self.write_reg(rd, result)
                    self._update_flags(result)
                    self._emit_event(op, operands, f"{a} − {b} = {result}")

                case Opcode.IMUL:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    operands = [rd, ra, rb]
                    a, b = self.read_reg(ra), self.read_reg(rb)
                    result = a * b
                    self.write_reg(rd, result)
                    self._update_flags(result)
                    self._emit_event(op, operands, f"√guṇ — {a} × {b} = {result}")

                case Opcode.IDIV:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    operands = [rd, ra, rb]
                    a, b = self.read_reg(ra), self.read_reg(rb)
                    if b == 0:
                        self._error = "शून्येन भाजने दोषः — division by zero"
                        self._halted = True
                    else:
                        result = int(a / b)
                        self.write_reg(rd, result)
                        self._update_flags(result)
                    self._emit_event(op, operands, f"√bhāj — {a} ÷ {b}")

                case Opcode.IMOD:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    operands = [rd, ra, rb]
                    a, b = self.read_reg(ra), self.read_reg(rb)
                    if b == 0:
                        self._error = "शून्येन शेषोद्देशे दोषः — modulo by zero"
                        self._halted = True
                    else:
                        result = a % b
                        self.write_reg(rd, result)
                        self._update_flags(result)
                    self._emit_event(op, operands, f"śeṣa — {a} % {b}")

                case Opcode.INEG:
                    r = self._read_byte()
                    operands = [r]
                    result = -self.read_reg(r)
                    self.write_reg(r, result)
                    self._update_flags(result)
                    self._emit_event(op, operands, f"viparyaya — R{r} = {result}")

                case Opcode.INC:
                    r = self._read_byte()
                    operands = [r]
                    result = self.read_reg(r) + 1
                    self.write_reg(r, result)
                    self._update_flags(result)
                    self._emit_event(op, operands, f"pluta — R{r} = {result}")

                case Opcode.DEC:
                    r = self._read_byte()
                    operands = [r]
                    result = self.read_reg(r) - 1
                    self.write_reg(r, result)
                    self._update_flags(result)
                    self._emit_event(op, operands, f"hrāsa — R{r} = {result}")

                case Opcode.IAND:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = self.read_reg(ra) & self.read_reg(rb)
                    self.write_reg(rd, result)
                    self._update_flags(result)
                    operands = [rd, ra, rb]

                case Opcode.IOR:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = self.read_reg(ra) | self.read_reg(rb)
                    self.write_reg(rd, result)
                    self._update_flags(result)
                    operands = [rd, ra, rb]

                case Opcode.IXOR:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = self.read_reg(ra) ^ self.read_reg(rb)
                    self.write_reg(rd, result)
                    self._update_flags(result)
                    operands = [rd, ra, rb]

                case Opcode.INOT:
                    r = self._read_byte()
                    result = ~self.read_reg(r)
                    self.write_reg(r, result)
                    operands = [r]

                case Opcode.ICMP:
                    ra, rb = self._read_byte(), self._read_byte()
                    operands = [ra, rb]
                    a, b = self.read_reg(ra), self.read_reg(rb)
                    self._flag_zero = a == b
                    self._flag_negative = a < b
                    self._emit_event(op, operands, f"tulya — {a} cmp {b}")

                case Opcode.CMP:
                    ra, rb = self._read_byte(), self._read_byte()
                    operands = [ra, rb]
                    diff = self.read_reg(ra) - self.read_reg(rb)
                    self._update_flags(diff)

                case Opcode.IEQ:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = 1 if self.read_reg(ra) == self.read_reg(rb) else 0
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.ILT:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = 1 if self.read_reg(ra) < self.read_reg(rb) else 0
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.ILE:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = 1 if self.read_reg(ra) <= self.read_reg(rb) else 0
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.IGT:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = 1 if self.read_reg(ra) > self.read_reg(rb) else 0
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.IGE:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = 1 if self.read_reg(ra) >= self.read_reg(rb) else 0
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.TEST:
                    r = self._read_byte()
                    val = self.read_reg(r)
                    self._flag_zero = val == 0
                    operands = [r]

                case Opcode.PUSH:
                    r = self._read_byte()
                    operands = [r]
                    self.push(self.read_reg(r))
                    self._emit_event(op, operands, f"√hṛ — push {self.read_reg(r)}")

                case Opcode.POP:
                    r = self._read_byte()
                    operands = [r]
                    val = self.pop()
                    self.write_reg(r, val)
                    self._emit_event(op, operands, f"pop → R{r} = {val}")

                case Opcode.DUP:
                    if self._data_stack:
                        self.push(self._data_stack[-1])
                    self._emit_event(op, [], "duplicate stack top")

                case Opcode.SWAP:
                    if len(self._data_stack) >= 2:
                        self._data_stack[-1], self._data_stack[-2] = (
                            self._data_stack[-2], self._data_stack[-1]
                        )
                    self._emit_event(op, [], "swap stack top")

                case Opcode.ROT:
                    if len(self._data_stack) >= 3:
                        a, b, c = (
                            self._data_stack[-3],
                            self._data_stack[-2],
                            self._data_stack[-1],
                        )
                        self._data_stack[-3] = b
                        self._data_stack[-2] = c
                        self._data_stack[-1] = a
                    self._emit_event(op, [], "rotate stack top-3")

                case Opcode.JMP:
                    addr = self._read_u16()
                    operands = [addr]
                    self._pc = addr
                    self._emit_event(op, operands, f"√gam — jump to 0x{addr:04x}")

                case Opcode.JZ:
                    r = self._read_byte()
                    addr = self._read_u16()
                    operands = [r, addr]
                    if self.read_reg(r) == 0:
                        self._pc = addr
                    self._emit_event(op, operands, f"JZ R{r} → {'0x%04x' % addr}")

                case Opcode.JNZ:
                    r = self._read_byte()
                    addr = self._read_u16()
                    operands = [r, addr]
                    if self.read_reg(r) != 0:
                        self._pc = addr
                    self._emit_event(op, operands, f"JNZ R{r} → {'0x%04x' % addr}")

                case Opcode.JE:
                    addr = self._read_u16()
                    operands = [addr]
                    if self._flag_zero:
                        self._pc = addr
                    self._emit_event(op, operands, f"JE → {'0x%04x' % addr}")

                case Opcode.JNE:
                    addr = self._read_u16()
                    operands = [addr]
                    if not self._flag_zero:
                        self._pc = addr
                    self._emit_event(op, operands, f"JNE → {'0x%04x' % addr}")

                case Opcode.CALL:
                    addr = self._read_u16()
                    operands = [addr]
                    self._call_stack.append(self._pc)
                    self._pc = addr
                    self._emit_event(op, operands, f"√kṛ — call 0x{addr:04x}")

                case Opcode.CALL_IND:
                    r = self._read_byte()
                    operands = [r]
                    addr = self.read_reg(r)
                    self._call_stack.append(self._pc)
                    self._pc = addr
                    self._emit_event(op, operands, f"√kṛ — call *R{r} → 0x{addr:04x}")

                case Opcode.RET:
                    addr = self._call_stack.pop() if self._call_stack else 0
                    self._pc = addr
                    self._emit_event(op, [], f"return to 0x{addr:04x}")

                case Opcode.FADD:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    # Simplified: treat as integer add for now
                    result = self.read_reg(ra) + self.read_reg(rb)
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.FSUB:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = self.read_reg(ra) - self.read_reg(rb)
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.FMUL:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    result = self.read_reg(ra) * self.read_reg(rb)
                    self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                case Opcode.FDIV:
                    rd, ra, rb = self._read_byte(), self._read_byte(), self._read_byte()
                    b = self.read_reg(rb)
                    if b == 0:
                        self._error = "division by zero"
                        self._halted = True
                    else:
                        result = self.read_reg(ra) // b
                        self.write_reg(rd, result)
                    operands = [rd, ra, rb]

                # --- A2A Agent Protocol Instructions ---

                case Opcode.TELL:
                    r = self._read_byte()
                    operands = [r]
                    message = {
                        "type": "TELL",
                        "from": self._current_agent,
                        "value": self.read_reg(r),
                        "scope": "sambodhana",
                    }
                    self._a2a_messages.append(message)
                    self._emit_event(op, operands, f"√brū — TELL: {message}")

                case Opcode.ASK:
                    r = self._read_byte()
                    operands = [r]
                    message = {
                        "type": "ASK",
                        "from": self._current_agent,
                        "register": r,
                        "scope": "sambodhana",
                    }
                    self._a2a_messages.append(message)
                    self._emit_event(op, operands, f"√pṛcch — ASK: {message}")

                case Opcode.DELEGATE:
                    r = self._read_byte()
                    operands = [r]
                    message = {
                        "type": "DELEGATE",
                        "from": self._current_agent,
                        "target_register": r,
                        "value": self.read_reg(r),
                    }
                    self._a2a_messages.append(message)
                    self._emit_event(op, operands, f"√niyuj — DELEGATE: {message}")

                case Opcode.BROADCAST:
                    r = self._read_byte()
                    operands = [r]
                    message = {
                        "type": "BROADCAST",
                        "from": self._current_agent,
                        "value": self.read_reg(r),
                    }
                    self._a2a_messages.append(message)
                    self._emit_event(op, operands, f"√prakaraṇ — BROADCAST: {message}")

                case Opcode.TRUST_CHECK:
                    r = self._read_byte()
                    operands = [r]
                    agent_id = self.read_reg(r)
                    is_trusted = self._is_trusted(
                        self._current_agent, str(agent_id)
                    )
                    self.write_reg(r, 1 if is_trusted else 0)
                    self._update_flags(1 if is_trusted else 0)
                    self._emit_event(
                        op, operands,
                        f"√adhi-īś — trust check: {is_trusted}"
                    )

                case Opcode.CAP_REQUIRE:
                    r = self._read_byte()
                    operands = [r]
                    has_cap = self._has_capability(
                        self._current_agent, "read", r
                    )
                    if not has_cap:
                        self._error = (
                            f"अधिकाराभावः — capability not held for R{r} "
                            f"by agent {self._current_agent!r}"
                        )
                        self._halted = True
                    self._emit_event(
                        op, operands,
                        f"√śakti — cap check R{r}: {has_cap}"
                    )

                # --- I/O ---

                case Opcode.PRINT:
                    r = self._read_byte()
                    operands = [r]
                    val = self.read_reg(r)
                    self._print_output = val
                    self._log_trace(f"darśaya — R{r} = {val}")
                    self._emit_event(op, operands, f"darśaya — {val}")

                case Opcode.HALT:
                    self._halted = True
                    self._emit_event(op, [], "√sthā — virāma (halt)")

                case _:
                    # Unknown opcode — skip
                    self._pc = start_pc + 1

        # Build result
        return VMResult(
            success=self._error is None,
            result=self._registers[0].value if self._registers else 0,
            registers=self.registers,
            cycles=self._cycles,
            error=self._error,
            halted=self._halted,
            trace=self._trace_log,
            events=self._events,
            scope_violations=self._scope_violations,
            a2a_messages=self._a2a_messages,
        )

    def _skip_instruction(self) -> None:
        """Skip the current instruction without executing (for lakāra gating)."""
        bc = self._bytecode
        if self._pc >= len(bc):
            return

        op_val = bc[self._pc]
        op = Opcode(op_val) if op_val in OPCODE_NAMES else None
        self._pc += 1

        if op is None:
            return

        # Advance PC past operands based on opcode format
        match op:
            case (Opcode.MOV | Opcode.LOAD | Opcode.STORE
                  | Opcode.ICMP | Opcode.CMP | Opcode.CALL_IND
                  | Opcode.PUSH | Opcode.POP):
                self._pc += 2
            case (Opcode.IADD | Opcode.ISUB | Opcode.IMUL
                  | Opcode.IDIV | Opcode.IMOD
                  | Opcode.IAND | Opcode.IOR | Opcode.IXOR
                  | Opcode.IEQ | Opcode.ILT | Opcode.ILE | Opcode.IGT | Opcode.IGE):
                self._pc += 3
            case Opcode.MOVI:
                self._pc += 3  # reg + u16
            case (Opcode.JZ | Opcode.JNZ):
                self._pc += 3  # reg + u16
            case (Opcode.JMP | Opcode.JE | Opcode.JNE | Opcode.CALL):
                self._pc += 2  # u16 address
            case (Opcode.PRINT | Opcode.TELL | Opcode.ASK
                  | Opcode.DELEGATE | Opcode.BROADCAST
                  | Opcode.TRUST_CHECK | Opcode.CAP_REQUIRE
                  | Opcode.INEG | Opcode.INC | Opcode.DEC | Opcode.RET
                  | Opcode.INOT | Opcode.TEST):
                self._pc += 1
            case _:
                pass

    @property
    def _max_cycles_internal(self) -> int:
        return self.DEFAULT_MAX_CYCLES

    # ---- State snapshot ----

    def get_state(self) -> dict[str, Any]:
        """Return a snapshot of the VM state."""
        return {
            "registers": self.registers,
            "register_scopes": [
                self._registers[i].scope.name for i in range(self.NUM_REGISTERS)
            ],
            "flags": {
                "zero": self._flag_zero,
                "negative": self._flag_negative,
                "carry": self._flag_carry,
            },
            "stack_depth": self.stack_depth,
            "pc": self._pc,
            "halted": self._halted,
            "cycles": self._cycles,
            "error": self._error,
            "lakara": self._current_lakara.name,
            "agent": self._current_agent,
            "region": self._current_region,
        }

    # ---- Register table display ----

    def register_table(self) -> str:
        """Return a formatted table of all registers with their scope info."""
        lines = [
            "╔══════════════════════════════════════════════════════════════════╗",
            "║  FLUX-san Register File — प्रवाहिनी अवस्थासञ्चयः               ║",
            "╠══════╦═══════════════╦══════════╦═══════════╦═══════════════════╣",
            "║  Reg  ║ Devanāgarī   ║ Value   ║ Scope     ║ Owner / Region     ║",
            "╠══════╬═══════════════╬══════════╬═══════════╬═══════════════════╣",
        ]
        for i in range(min(self.NUM_REGISTERS, 16)):  # Show first 16
            reg = self._registers[i]
            dev = register_devanagari(i)
            owner_str = reg.owner or "—"
            if reg.scope == Vibhakti.SAPTAMI:
                owner_str = f"region={reg.region}"
            lines.append(
                f"║  R{i:<3d} ║ {dev:<13s} ║ {reg.value:>7d} ║ "
                f"{reg.scope.devanagari:<9s} ║ {owner_str:<19s} ║"
            )
        if self.NUM_REGISTERS > 16:
            lines.append(f"║  ...  ║ ({self.NUM_REGISTERS - 16} more registers hidden)                       ║")
        lines.append("╚══════╩═══════════════╩══════════╩═══════════╩═══════════════════╝")
        return "\n".join(lines)

    # ---- Reset ----

    def reset(self) -> None:
        """Reset the VM to initial state."""
        self._registers = [
            ScopedRegister(index=i) for i in range(self.NUM_REGISTERS)
        ]
        self._call_stack.clear()
        self._data_stack.clear()
        self._flag_zero = False
        self._flag_negative = False
        self._flag_carry = False
        self._pc = 0
        self._halted = False
        self._cycles = 0
        self._error = None
        self._bytecode = bytearray()
        self._trace_log.clear()
        self._events.clear()
        self._scope_violations.clear()
        self._a2a_messages.clear()
        self._capabilities.clear()
        self._trust_store.clear()
        self._region_members.clear()
        self._print_output = None
        self._current_lakara = Lakara.LAT
        self._lakara_context = LakaraDetector.make_context(Lakara.LAT)
