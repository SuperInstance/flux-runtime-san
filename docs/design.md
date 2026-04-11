# FLUX-san Design Document
# प्रवाहिनी-संरचनाविवरणम्

## 1. परिचयः — Introduction

FLUX-san (प्रवाहिनी) is a Sanskrit-first natural language runtime for the FLUX universal bytecode VM. The core insight is:

> **Pāṇini's Aṣṭādhyāyī IS a type system.**

Sanskrit's grammar, codified ~2,400 years ago, provides:
- **Formal rule-based derivation** (3,959 sūtras on 1,700 elements)
- **Marker-based typing** (anubandhas → type annotations)
- **Technical terminology** (saṃjñās → type names)
- **Meta-rule composition** (paribhāṣās → compiler passes)

## 2. विभक्तिः → Scope System (8 Cases = 8 Scopes)

### Design Principle

Each of Sanskrit's 8 vibhaktis (grammatical cases) maps to a distinct bytecode access pattern. When a noun appears in a particular case, it acquires a specific scope level that determines how the FLUX VM handles memory access for that entity.

### Case-to-Scope Mapping

```
┌───────────┬─────────────┬────────────────┬─────────────────────────┐
│ Case      │ Sanskrit    │ Scope          │ Bytecode Pattern        │
├───────────┼─────────────┼────────────────┼─────────────────────────┤
│ 1st       │ प्रथमा      │ PUBLIC         │ MOV R0, Rn              │
│ 2nd       │ द्वितीया    │ OBJECT         │ LOAD R0, Rn             │
│ 3rd       │ तृतीया      │ FUNCTION       │ CALL Rn                 │
│ 4th       │ चतुर्थी     │ CAPABILITY     │ CAP_REQ R0, Rn          │
│ 5th       │ पञ्चमी      │ ORIGIN         │ STORE Rn, R0            │
│ 6th       │ षष्ठी       │ OWNERSHIP      │ IOR R0, Rn              │
│ 7th       │ सप्तमी      │ CONTEXT        │ REGION_ENTER; MOV R0, Rn│
│ 8th       │ सम्बोधन    │ INVOCATION     │ TELL Rn (A2A)           │
└───────────┴─────────────┴────────────────┴─────────────────────────┘
```

### Implementation

The `Vibhakti` enum provides 8 case values. Each has:
- `devanagari` — Name in Devanāgarī script
- `iast` — Name in IAST transliteration
- `english` — English grammatical term
- `scope` — Mapped `ScopeLevel` for FLUX bytecode

`ScopedAccess` objects wrap register accesses with vibhakti qualifiers, generating appropriate bytecode patterns.

`VibhaktiValidator` detects case from word endings using terminal suffix patterns (śabda-rūpāṇi).

## 3. लकारः → Execution Modes (8 Tenses = 8 Strategies)

### Design Principle

Sanskrit's lakāras (tense/mood markers) determine not just *when* an action happens, but *how* it executes. Each lakāra selects a distinct FLUX execution strategy.

### Lakāra-to-Mode Mapping

```
┌──────────┬──────────────┬───────────────┬─────────────────────────┐
│ Lakāra   │ Sanskrit     │ Mode          │ Behavior                │
├──────────┼──────────────┼───────────────┼─────────────────────────┤
│ laṭ      │ लट्         │ NORMAL        │ Sequential execution    │
│ laṅ      │ लङ्         │ CONDITIONAL   │ Branch on condition     │
│ liṭ      │ लिट्         │ VERIFIED      │ Cached/verified result  │
│ luṅ      │ लुङ्         │ ATOMIC        │ Immediate, uninterrupt.  │
│ lṛṭ      │ लृट्         │ DEFERRED      │ Future/lazy execution   │
│ lṛṅ      │ लृङ्         │ CONDITIONAL   │ Speculative branch      │
│ vidhiliṅ │ विधिलिङ्    │ SPECULATIVE   │ Try with rollback       │
│ āśīrliṅ  │ आशीर्लिङ्   │ FORCED        │ Override all guards     │
└──────────┴──────────────┴───────────────┴─────────────────────────┘
```

### Implementation

`Lakara` enum provides 8 tense/mood values. `LakaraContext` wraps execution with a lakāra qualifier, controlling:
- `should_execute` — Whether the action runs
- `bytecode_prefix` — Instruction modifier (COND, VERIFY, ATOMIC, etc.)

`LakaraDetector` identifies lakāra from verbal endings and explicit markers.

## 4. समासः → Type Composition (Compounds = Types)

### Design Principle

Sanskrit's samāsa (compound word) system maps directly to type-theoretic composition:

```
┌──────────────────┬─────────────┬─────────────────────────────────┐
│ Samāsa           │ Sanskrit    │ Type Theory                     │
├──────────────────┼─────────────┼─────────────────────────────────┤
│ dvandva          │ द्वन्द्व    │ Tuple[A, B] | Union[A, B]      │
│ karmadhāraya     │ कर्मधारय  │ A & B (intersection / product) │
│ bahuvrīhi        │ बहुव्रीहि  │ ∃x. P(x) (dependent/exist.)   │
└──────────────────┴─────────────┴─────────────────────────────────┘
```

### Type-Theoretic Mapping

- **dvandva** (coordinate): A + B → `Tuple[A, B]` or `Union[A, B]` — two things combined equally
- **karmadhāraya** (determinative): The first modifies the second → `Intersection[A, B]` or product type — the compound has both qualities
- **bahuvrīhi** (possessive): The compound refers to something external → `∃x. P(x)` — dependent type where the referent is contextually determined

### Implementation

`SamasaParser` splits compound words using:
1. Known compound dictionary lookup
2. Conjunction marker detection (ca, vā, uta → dvandva)
3. Possessive suffix detection (vat, mat, in → bahuvrīhi)
4. Simple sandhi splitting

`TypeComposition` generates type expressions from samāsa structure.

## 5. द्विवचन → Pairwise Operations (Dual Number = Arity 2)

### Design Principle

Sanskrit is one of the few languages with a grammatical dual number (dvivacana). This maps to pairwise operations — operating on exactly two elements.

### Implementation

`FluxInterpreterSan.pairwise_op(values, op)` applies an operation between adjacent pairs:
- `[a, b, c, d]` → `[a⊕b, b⊕c, c⊕d]`
- Supports: add, sub, mul, div, mod

## 6. सन्धिः → Token Fusion/Splitting (Sandhi Resolution)

### Design Principle

Sanskrit's sandhi (phonological fusion) creates compound tokens from individual words. For the interpreter, sandhi resolution is the equivalent of lexer preprocessing — splitting fused tokens back into component words.

### Implementation

`SamasaParser.split_sandhi_simple()` handles:
- Vowel sandhi: a + a → ā
- Semi-vowel sandhi: i + a → ya, u + a → va
- Visarga sandhi: aḥ before vowel → ar/ass

Full sandhi resolution would require implementing all Pāṇinian paribhāṣā rules.

## 7. FLUX VM — 64-Register, Stack-Based

### Architecture

The FLUX VM (matching the TypeScript reference implementation):
- **64 registers** (R0-R63), 32-bit signed integers
- **Stack** for push/pop/dup/swap operations
- **Flags**: zero, negative (for conditional branching)
- **Bytecode**: variable-length encoding (1-4 bytes per instruction)
- **Opcodes**: 0x00-0xFF covering arithmetic, bitwise, comparison, flow control, stack, float, string, and A2A protocol

### Key Opcodes

```
0x00 NOP       0x08 IADD      0x0A IMUL      0x0B IDIV
0x01 MOV       0x09 ISUB      0x0C IMOD      0x2B MOVI
0x02 LOAD      0x0D INEG      0x0E INC       0x0F DEC
0x03 STORE     0x18 ICMP      0x20 PUSH      0x21 POP
0x04 JMP       0x28 RET       0x60 TELL      0xFF HALT
```

## 8. शब्दावली — Vocabulary Files

### math.ese (गणितशब्दावली)

Mathematical operations mapped to Sanskrit verbs:
- `gaṇaya` (गणय) = add, `guṇa` (गुण) = multiply
- `śoṣa` (शोष) = subtract, `bhāj` (भाज) = divide
- Sanskrit number words: eka (1), dvi (2), ... daśa (10), śata (100)

### a2a.ese (अजेन्त-शब्दावली)

Agent-to-agent protocol mapped to Sanskrit verbs:
- `brūhi` (बृहि) = TELL, `pṛccha` (पृच्छ) = ASK
- `niyujya` (नियुज्य) = DELEGATE
- Uses vibhakti system: sambodhana (vocative) = A2A invocation

## 9. सर्वाङ्गिणी-संरचना (File Structure)

```
flux-runtime-san/
├── README.md                           # Sanskrit + English documentation
├── pyproject.toml                      # Python package config
├── src/
│   └── flux_san/
│       ├── __init__.py                 # Package exports
│       ├── cli.py                      # CLI (नमस्कार, निर्मा, चालय, विच्छेद)
│       ├── interpreter.py             # NL interpreter + FLUX VM
│       ├── vibhakti.py                 # 8-case scope system
│       ├── lakara.py                   # 8 execution modes
│       ├── samasa.py                   # Compound parser / type composer
│       └── vocabulary/
│           ├── math.ese                # Mathematical vocabulary
│           └── a2a.ese                 # A2A agent vocabulary
├── tests/
│   └── test_interpreter_san.py         # 55+ tests
└── docs/
    └── design.md                       # This design document
```

## 10. भाविकार्याणि (Future Work)

- Full sandhi resolution (all Pāṇinian rules)
- Verb conjugation for lakāra detection
- द्वन्द्व (dvandva) dual number in function arity
- तृतीया (instrumental) as function composition
- बहुव्रीहि (bahuvrīhi) as dependent types with proofs
- Devanāgarī script input (not just IAST)
- Full A2A agent protocol implementation
- धातु (verbal root) → opcode mapping
- प्रत्यय (suffix) → type annotation system
