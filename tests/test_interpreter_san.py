"""
Tests for FLUX-san — Sanskrit-first FLUX Runtime
===================================================
Comprehensive tests covering:
  - Vibhakti (8-case scope system)
  - Lakāra (8 execution modes)
  - Samāsa (compound parser / type composition)
  - Interpreter Sanskrit NL patterns
  - VM bytecode execution
  - Sandhi resolution
  - Dual number (pairwise operations)
  - Sanskrit number words
"""

import pytest

from flux_san.vibhakti import (
    Vibhakti, ScopeLevel, VibhaktiValidator, ScopedAccess,
)
from flux_san.lakara import (
    Lakara, ExecutionMode, LakaraDetector, LakaraContext,
)
from flux_san.samasa import (
    SamasaType, SamasaParser, Compound, TypeComposition,
)
from flux_san.interpreter import (
    FluxVM, FluxInterpreterSan, Op, sanskrit_num_to_int,
    SANSKRIT_NUMBERS, OP_NAMES,
)


# ============================================================
# 1. VIBHAKTI TESTS (विभक्तिपरीक्षा)
# ============================================================

class TestVibhakti:
    """Tests for the Aṣṭau-vibhakti (8-case scope system)."""

    def test_vibhakti_count(self):
        """There should be exactly 8 cases."""
        assert len(Vibhakti) == 8

    def test_prathama_is_public_scope(self):
        """प्रथमा (nominative) maps to PUBLIC scope."""
        assert Vibhakti.PRATHAMA.scope == ScopeLevel.PUBLIC

    def test_dvitiya_is_object_scope(self):
        """द्वितीया (accusative) maps to OBJECT scope."""
        assert Vibhakti.DVITIYA.scope == ScopeLevel.OBJECT

    def test_tritiya_is_function_scope(self):
        """तृतीया (instrumental) maps to FUNCTION scope."""
        assert Vibhakti.TRITIYA.scope == ScopeLevel.FUNCTION

    def test_chaturthi_is_capability_scope(self):
        """चतुर्थी (dative) maps to CAPABILITY scope."""
        assert Vibhakti.CHATURTHI.scope == ScopeLevel.CAPABILITY

    def test_panchami_is_origin_scope(self):
        """पञ्चमी (ablative) maps to ORIGIN scope."""
        assert Vibhakti.PANCHAMI.scope == ScopeLevel.ORIGIN

    def test_shashthi_is_ownership_scope(self):
        """षष्ठी (genitive) maps to OWNERSHIP scope."""
        assert Vibhakti.SHASHTHI.scope == ScopeLevel.OWNERSHIP

    def test_saptami_is_context_scope(self):
        """सप्तमी (locative) maps to CONTEXT scope."""
        assert Vibhakti.SAPTAMI.scope == ScopeLevel.CONTEXT

    def test_sambodhana_is_invocation_scope(self):
        """सम्बोधन (vocative) maps to INVOCATION (A2A) scope."""
        assert Vibhakti.SAMBODHANA.scope == ScopeLevel.INVOCATION

    def test_devanagari_names(self):
        """Each vibhakti has a Devanāgarī name."""
        assert Vibhakti.PRATHAMA.devanagari == "प्रथमा"
        assert Vibhakti.SAMBODHANA.devanagari == "सम्बोधन"

    def test_iast_names(self):
        """Each vibhakti has an IAST name."""
        assert Vibhakti.TRITIYA.iast == "tṛtīyā"
        assert Vibhakti.CHATURTHI.iast == "caturthī"

    def test_scoped_access_public(self):
        """Public scope generates MOV pattern."""
        sa = ScopedAccess(register=5, vibhakti=Vibhakti.PRATHAMA)
        assert sa.scope_level == ScopeLevel.PUBLIC
        assert "MOV" in sa.access_pattern

    def test_scoped_access_invocation(self):
        """Invocation scope generates TELL (A2A) pattern."""
        sa = ScopedAccess(register=3, vibhakti=Vibhakti.SAMBODHANA)
        assert sa.scope_level == ScopeLevel.INVOCATION
        assert "TELL" in sa.access_pattern

    def test_vibhakti_table(self):
        """Case table renders without error."""
        table = VibhaktiValidator.all_cases_table()
        assert "प्रथमा" in table
        assert "सम्बोधन" in table
        assert "PUBLIC" in table
        assert "INVOCATION" in table

    def test_detect_vibhakti_nominative(self):
        """Detect prathamā from '-aḥ' ending."""
        result = VibhaktiValidator.detect_vibhakti("rāmaḥ")
        # rāmaḥ ends with aḥ → could be prathamā
        assert result is not None

    def test_scope_levels_count(self):
        """There should be exactly 8 scope levels."""
        assert len(ScopeLevel) == 8


# ============================================================
# 2. LAKARA TESTS (कालपरीक्षा)
# ============================================================

class TestLakara:
    """Tests for the Aṣṭau-lakāra (8 execution modes)."""

    def test_lakara_count(self):
        """There should be exactly 8 lakāras."""
        assert len(Lakara) == 8

    def test_lat_is_normal(self):
        """लट् (laṭ, present) maps to NORMAL execution."""
        assert Lakara.LAT.execution_mode == ExecutionMode.NORMAL

    def test_lan_is_conditional(self):
        """लङ् (laṅ, imperfect) maps to CONDITIONAL execution."""
        assert Lakara.LAN.execution_mode == ExecutionMode.CONDITIONAL

    def test_lit_is_verified(self):
        """लिट् (liṭ, perfect) maps to VERIFIED execution."""
        assert Lakara.LIT.execution_mode == ExecutionMode.VERIFIED

    def test_lun_is_atomic(self):
        """लुङ् (luṅ, aorist) maps to ATOMIC execution."""
        assert Lakara.LUN.execution_mode == ExecutionMode.ATOMIC

    def test_lrit_is_deferred(self):
        """लृट् (lṛṭ, future) maps to DEFERRED execution."""
        assert Lakara.LRIT.execution_mode == ExecutionMode.DEFERRED

    def test_vidhiling_is_speculative(self):
        """विधिलिङ् (vidhiliṅ, potential) maps to SPECULATIVE."""
        assert Lakara.VIDHILING.execution_mode == ExecutionMode.SPECULATIVE

    def test_asirling_is_forced(self):
        """आशीर्लिङ् (āśīrliṅ, imperative) maps to FORCED execution."""
        assert Lakara.ASIRLING.execution_mode == ExecutionMode.FORCED

    def test_devanagari_names(self):
        """Each lakāra has a Devanāgarī name."""
        assert Lakara.LAT.devanagari == "लट्"
        assert Lakara.ASIRLING.devanagari == "आशीर्लिङ्"

    def test_lakara_context_normal(self):
        """Normal lakāra context always executes."""
        ctx = LakaraContext(lakara=Lakara.LAT)
        assert ctx.should_execute is True
        assert ctx.bytecode_prefix == ""

    def test_lakara_context_conditional_true(self):
        """Conditional with True condition should execute."""
        ctx = LakaraContext(lakara=Lakara.LAN, condition=True)
        assert ctx.should_execute is True
        assert ctx.bytecode_prefix == "COND "

    def test_lakara_context_conditional_false(self):
        """Conditional with False condition should not execute."""
        ctx = LakaraContext(lakara=Lakara.LAN, condition=False)
        assert ctx.should_execute is False

    def test_lakara_context_deferred(self):
        """Deferred lakāra never executes immediately."""
        ctx = LakaraContext(lakara=Lakara.LRIT)
        assert ctx.should_execute is False
        assert ctx.bytecode_prefix == "DEFER "

    def test_lakara_context_forced(self):
        """Forced lakāra always executes."""
        ctx = LakaraContext(lakara=Lakara.ASIRLING)
        assert ctx.should_execute is True
        assert ctx.bytecode_prefix == "FORCE "

    def test_lakara_table(self):
        """Lakāra table renders without error."""
        table = LakaraDetector.all_lakaras_table()
        assert "लट्" in table
        assert "FORCED" in table

    def test_execution_modes_count(self):
        """There should be exactly 7 execution modes."""
        assert len(ExecutionMode) == 7


# ============================================================
# 3. SAMASA TESTS (समासपरीक्षा)
# ============================================================

class TestSamasa:
    """Tests for the Samāsa (compound) parser and type composer."""

    def test_samasa_types_count(self):
        """There should be exactly 3 samāsa types."""
        assert len(SamasaType) == 3

    def test_dvandva_is_tuple(self):
        """द्वन्द्व (dvandva) maps to Tuple type."""
        tc = TypeComposition(SamasaType.DVANDVA, "A", "B")
        assert "Tuple" in tc.composed_type

    def test_karmadhara_is_intersection(self):
        """कर्मधारय (karmadhāraya) maps to Intersection type."""
        tc = TypeComposition(SamasaType.KARMADHARAYA, "A", "B")
        assert "Intersection" in tc.composed_type

    def test_bahuvrihi_is_dependent(self):
        """बहुव्रीहि (bahuvrīhi) maps to Dependent/Existential type."""
        tc = TypeComposition(SamasaType.BAHUVRIHI, "A", "B")
        assert "Dependent" in tc.composed_type
        assert "∃" in tc.composed_type

    def test_parse_known_compound(self):
        """Parse known compound: rāśiyogaḥ (sum)."""
        result = SamasaParser.parse("rāśiyogaḥ")
        assert result is not None
        assert result.samasa_type == SamasaType.KARMADHARAYA
        assert "rāśi" in result.components

    def test_parse_gunayoga(self):
        """Parse guṇayogaḥ (multiplication compound)."""
        result = SamasaParser.parse("guṇayogaḥ")
        assert result is not None
        assert result.meaning == "multiplication"

    def test_parse_dvandva_with_ca(self):
        """Parse dvandva with 'ca' conjunction."""
        result = SamasaParser.parse("rāmaca")
        assert result is not None
        assert result.samasa_type == SamasaType.DVANDVA

    def test_sandhi_split_simple(self):
        """Simple sandhi splitting."""
        result = SamasaParser.split_sandhi_simple("testword")
        assert isinstance(result, list)

    def test_compound_binary(self):
        """A 2-component compound is binary (dvivacana)."""
        result = SamasaParser.parse("rāśiyogaḥ")
        assert result is not None
        assert result.is_binary

    def test_samasa_table(self):
        """Samāsa table renders without error."""
        table = SamasaParser.all_samasa_table()
        assert "द्वन्द्व" in table
        assert "Tuple" in table


# ============================================================
# 4. INTERPRETER TESTS (अनुवादकपरीक्षा)
# ============================================================

class TestInterpreter:
    """Tests for the Sanskrit NL interpreter."""

    def test_load_register(self):
        """Load value into register: load R1 saha 42."""
        interp = FluxInterpreterSan()
        result = interp.execute_line("load R1 saha 42")
        assert result.success
        assert interp.registers[1] == 42

    def test_add_registers(self):
        """Add two registers: gaṇaya R1 pluta R2."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 10)
        interp.set_register(2, 7)
        result = interp.execute_line("gaṇaya R1 pluta R2")
        assert result.success
        assert interp.registers[0] == 17

    def test_multiply_registers(self):
        """Multiply two registers: R1 guṇa R2."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 6)
        interp.set_register(2, 7)
        result = interp.execute_line("R1 guṇa R2")
        assert result.success
        assert interp.registers[0] == 42

    def test_subtract_registers(self):
        """Subtract: R1 śoṣa R2."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 15)
        interp.set_register(2, 3)
        result = interp.execute_line("R1 śoṣa R2")
        assert result.success
        assert interp.registers[0] == 12

    def test_divide_registers(self):
        """Divide: R1 bhāj R2."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 20)
        interp.set_register(2, 4)
        result = interp.execute_line("R1 bhāj R2")
        assert result.success
        assert interp.registers[0] == 5

    def test_divide_by_zero(self):
        """Division by zero produces Sanskrit error."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 10)
        interp.set_register(2, 0)
        result = interp.execute_line("R1 bhāj R2")
        assert not result.success
        assert result.error is not None

    def test_increment(self):
        """Increment: pluta R1."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 5)
        result = interp.execute_line("pluta R1")
        assert result.success
        assert interp.registers[1] == 6

    def test_decrement(self):
        """Decrement: hrāsa R1."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 5)
        result = interp.execute_line("hrāsa R1")
        assert result.success
        assert interp.registers[1] == 4

    def test_compare(self):
        """Compare: R1 tulya R2."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 10)
        interp.set_register(2, 10)
        result = interp.execute_line("R1 tulya R2")
        assert result.success

    def test_halt(self):
        """Halt: virāma."""
        interp = FluxInterpreterSan()
        result = interp.execute_line("virāma")
        assert result.success
        assert result.halted

    def test_push_pop(self):
        """Push then pop."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 99)
        interp.execute_line("juṣa R1")
        result = interp.execute_line("gṛhṇa R2")
        assert result.success
        assert interp.registers[2] == 99

    def test_range_sum(self):
        """Range sum: R1 itaḥ R2 paryantayogaḥ."""
        interp = FluxInterpreterSan()
        interp.set_register(1, 1)
        interp.set_register(2, 5)
        result = interp.execute_line("R1 itaḥ R2 paryantayogaḥ")
        assert result.success
        # Sum 1+2+3+4+5 = 15
        assert interp.registers[0] == 15

    def test_program_execution(self):
        """Execute multi-line program."""
        interp = FluxInterpreterSan()
        program = "load R1 saha 10\nload R2 saha 20\ngaṇaya R1 pluta R2"
        result = interp.quick_exec(program)
        assert result.success
        assert result.result == 30

    def test_unknown_pattern(self):
        """Unknown pattern returns Sanskrit error."""
        interp = FluxInterpreterSan()
        result = interp.execute_line("ajñātam vastu")
        assert not result.success
        assert "अज्ञातं" in result.error

    def test_empty_line(self):
        """Empty line succeeds without doing anything."""
        interp = FluxInterpreterSan()
        result = interp.execute_line("")
        assert result.success

    def test_comment_line(self):
        """Comment lines (starting with #) succeed."""
        interp = FluxInterpreterSan()
        result = interp.execute_line("# This is a comment")
        assert result.success

    def test_sandhi_resolution(self):
        """Sandhi split operation."""
        interp = FluxInterpreterSan()
        interp.execute_line("saṃdhi devāśva")
        parts = interp.sandhi_result()
        assert parts is not None

    def test_vibhakti_detection(self):
        """Vibhakti detection from word."""
        interp = FluxInterpreterSan()
        interp.execute_line("vibhakti ramasya")
        vb = interp.vibhakti_result()
        assert vb is not None


# ============================================================
# 5. VM TESTS (यन्त्रपरीक्षा)
# ============================================================

class TestVM:
    """Tests for the FLUX Virtual Machine."""

    def test_vm_init(self):
        """VM initializes with 64 zeroed registers."""
        vm = FluxVM()
        assert len(vm.regs) == 64
        assert all(r == 0 for r in vm.regs)

    def test_vm_halt(self):
        """HALT opcode stops execution."""
        vm = FluxVM(bytecode=bytearray([Op.HALT]))
        result = vm.execute()
        assert result.halted
        assert result.success

    def test_vm_mov(self):
        """MOV copies register value."""
        vm = FluxVM(bytecode=bytearray([Op.MOVI, 1, 42, 0, Op.MOV, 0, 1, Op.HALT]))
        vm.execute()
        assert vm.regs[0] == 42

    def test_vm_iadd(self):
        """IADD adds two registers."""
        vm = FluxVM(bytecode=bytearray([
            Op.MOVI, 1, 10, 0,
            Op.MOVI, 2, 25, 0,
            Op.IADD, 0, 1, 2,
            Op.HALT,
        ]))
        vm.execute()
        assert vm.regs[0] == 35

    def test_vm_imul(self):
        """IMUL multiplies two registers."""
        vm = FluxVM(bytecode=bytearray([
            Op.MOVI, 1, 6, 0,
            Op.MOVI, 2, 7, 0,
            Op.IMUL, 0, 1, 2,
            Op.HALT,
        ]))
        vm.execute()
        assert vm.regs[0] == 42

    def test_vm_push_pop(self):
        """PUSH then POP preserves value."""
        vm = FluxVM(bytecode=bytearray([
            Op.MOVI, 1, 99, 0,
            Op.PUSH, 1,
            Op.MOVI, 1, 0, 0,  # Clear R1
            Op.POP, 1,
            Op.HALT,
        ]))
        vm.execute()
        assert vm.regs[1] == 99

    def test_vm_jump(self):
        """JMP changes program counter."""
        vm = FluxVM(bytecode=bytearray([
            Op.MOVI, 0, 0, 0,       # PC=0
            Op.MOVI, 0, 0, 0,       # PC=4
            Op.MOVI, 0, 1, 0,       # PC=8: this sets R0=1
            Op.JMP, 8, 0,           # PC=11: jump to PC=8
        ]))
        # The JMP at offset 11 targets offset 8 which sets R0=1
        # This will loop and hit max_cycles
        vm.max_cycles = 500
        result = vm.execute()
        assert result.error is not None  # Max cycles exceeded

    def test_vm_state(self):
        """VM state snapshot."""
        vm = FluxVM()
        state = vm.get_state()
        assert len(state.registers) == 64
        assert state.halted is False


# ============================================================
# 6. DUAL NUMBER TESTS (द्विवचनपरीक्षा)
# ============================================================

class TestDvivacana:
    """Tests for dual number (dvivacana) / pairwise operations."""

    def test_pairwise_add(self):
        """Pairwise addition of values."""
        result = FluxInterpreterSan.pairwise_op([1, 3, 5, 7], "add")
        assert result == [4, 8, 12]

    def test_pairwise_sub(self):
        """Pairwise subtraction of values."""
        result = FluxInterpreterSan.pairwise_op([10, 3, 7], "sub")
        assert result == [7, -4]

    def test_pairwise_mul(self):
        """Pairwise multiplication."""
        result = FluxInterpreterSan.pairwise_op([2, 3, 4], "mul")
        assert result == [6, 12]

    def test_pairwise_single(self):
        """Single value produces no pairwise result."""
        result = FluxInterpreterSan.pairwise_op([42], "add")
        assert result == []

    def test_pairwise_empty(self):
        """Empty list produces no pairwise result."""
        result = FluxInterpreterSan.pairwise_op([], "add")
        assert result == []


# ============================================================
# 7. SANSKRIT NUMBER TESTS (सङ्ख्यापरीक्षा)
# ============================================================

class TestSanskritNumbers:
    """Tests for Sanskrit number word conversions."""

    def test_zero(self):
        """शून्य = 0."""
        assert sanskrit_num_to_int("śūnya") == 0

    def test_one(self):
        """एक = 1."""
        assert sanskrit_num_to_int("eka") == 1

    def test_two(self):
        """द्वि = 2."""
        assert sanskrit_num_to_int("dvi") == 2

    def test_ten(self):
        """दश = 10."""
        assert sanskrit_num_to_int("daśa") == 10

    def test_hundred(self):
        """शत = 100."""
        assert sanskrit_num_to_int("śata") == 100

    def test_thousand(self):
        """सहस्र = 1000."""
        assert sanskrit_num_to_int("sahasra") == 1000

    def test_unknown_number(self):
        """Unknown number word returns None."""
        assert sanskrit_num_to_int("gajapati") is None

    def test_number_vocabulary_complete(self):
        """Number vocabulary has expected entries."""
        assert "eka" in SANSKRIT_NUMBERS
        assert "daśa" in SANSKRIT_NUMBERS
        assert "śata" in SANSKRIT_NUMBERS
        assert "sahasra" in SANSKRIT_NUMBERS


# ============================================================
# 8. OPCODE TESTS (सङ्केतपरीक्षा)
# ============================================================

class TestOpcodes:
    """Tests for the FLUX opcode definitions."""

    def test_halt_opcode(self):
        """HALT is 0xFF."""
        assert Op.HALT == 0xFF

    def test_print_opcode(self):
        """PRINT is 0xFE."""
        assert Op.PRINT == 0xFE

    def test_iadd_opcode(self):
        """IADD is 0x08."""
        assert Op.IADD == 0x08

    def test_tell_opcode(self):
        """TELL (A2A) is 0x60."""
        assert Op.TELL == 0x60

    def test_op_names_complete(self):
        """OP_NAMES contains key opcodes."""
        assert 0x00 in OP_NAMES  # NOP
        assert 0xFF in OP_NAMES  # HALT
        assert 0x60 in OP_NAMES  # TELL
        assert 0x65 in OP_NAMES  # CAP_REQ
