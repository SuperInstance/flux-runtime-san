# प्रवाहिनी — FLUX-san

# FLUX — प्रवाहिनी भाषा सार्वभौमिक निष्पादनम्
# Pravāhinī — Bhāṣā Sārvabhaumika Niṣpādanam
# Fluent Language Universal Execution — Sanskrit-first Natural Language Runtime

> **पाणिनेः व्याकरणम् एव प्रकारविज्ञानम्** — Pāṇini's grammar IS a type system.

## परिचयः (Introduction)

FLUX-san is a Sanskrit-first natural language runtime for the FLUX universal bytecode VM. Sanskrit's grammar — codified in Pāṇini's Aṣṭādhyāyī with 3,959 rules operating on 1,700 elements through anubandhas (markers) and saṃjñās (technical terms) — is the most rigorously formalized natural language in human history. This makes Sanskrit the most natural language for programming.

## स्थापत्यम् (Architecture)

### Aṣṭau-vibhakti (8 Cases) → 8 Scope Levels

| # | विभक्तिः (Case) | English | FLUX Scope |
|---|----------------|---------|------------|
| 1 | प्रथमा (prathamā) | Nominative | PUBLIC — uncontrolled read |
| 2 | द्वितीया (dvitīyā) | Accusative | OBJECT — receives action |
| 3 | तृतीया (tṛtīyā) | Instrumental | FUNCTION — called as tool |
| 4 | चतुर्थी (caturthī) | Dative | CAPABILITY — permission grant |
| 5 | पञ्चमी (pañcamī) | Ablative | ORIGIN — export/source |
| 6 | षष्ठी (ṣaṣṭhī) | Genitive | OWNERSHIP — containment |
| 7 | सप्तमी (saptamī) | Locative | CONTEXT — in-region |
| 8 | सम्बोधन (sambodhana) | Vocative | INVOCATION — A2A call |

### Aṣṭau-lakāra (8 Tenses/Moods) → 8 Execution Modes

| # | लकारः (Lakāra) | English | FLUX Mode |
|---|---------------|---------|-----------|
| 1 | लट् (laṭ) | Present | NORMAL — sequential |
| 2 | लङ् (laṅ) | Imperfect | CONDITIONAL — branch |
| 3 | लिट् (liṭ) | Perfect | VERIFIED — cached |
| 4 | लुङ् (luṅ) | Aorist | ATOMIC — immediate |
| 5 | लृट् (lṛṭ) | Future | DEFERRED — lazy |
| 6 | लृङ् (lṛṅ) | Conditional | CONDITIONAL — speculative |
| 7 | विधिलिङ् (vidhiliṅ) | Potential | SPECULATIVE — try/rollback |
| 8 | आशीर्लिङ् (āśīrliṅ) | Imperative | FORCED — override guards |

### Samāsa (Compounds) → Type Composition

| समासः | Sanskrit | Type Theory |
|-------|----------|-------------|
| द्वन्द्व (dvandva) | Coordinate | `Tuple[A, B] \| Union[A, B]` |
| कर्मधारय (karmadhāraya) | Determinative | `A & B` (intersection) |
| बहुव्रीहि (bahuvrīhi) | Possessive | `∃x. P(x)` (existential) |

### Tri-vacana (3 Numbers) → Arity Types

| सङ्ख्या | Sanskrit | Arity |
|--------|----------|-------|
| एकवचन (ekavacana) | Singular | 1 |
| द्विवचन (dvivacana) | Dual | 2 (pairwise ops) |
| बहुवचन (bahuvacana) | Plural | N |

## संस्थापनम् (Installation)

```bash
pip install -e /path/to/flux-runtime-san
```

## उपयोगः (Usage)

### CLI Commands

```bash
# Show banner (नमस्कार)
flux-san namaskara

# Execute a program (चालय)
flux-san calaya program.san

# Show case system table (विभक्ति)
flux-san vibhakti

# Show execution modes table (कालः)
flux-san kala

# Show compound types (समासः)
flux-san samasa

# Resolve sandhi (संन्धि)
flux-san sandhi devāśva

# Run tests (परीक्षा)
flux-san pariksha

# Interactive REPL
flux-san
```

### Sanskrit NL Patterns (IAST)

```sanskrit
# Load values
load R1 saha 10        # लोड R1 सह 10
load R2 saha 20        # लोड R2 सह 20

# Arithmetic (गणितक्रियाः)
gaṇaya R1 pluta R2     # गणय R1 प्लुत R2 — Add → R0 = 30
R1 guṇa R2             # R1 गुण R2 — Multiply → R0 = 200
R1 śoṣa R2             # R1 शोष R2 — Subtract → R0 = -10
R1 bhāj R2             # R1 भाज R2 — Divide → R0 = 0

# Range sum (पर्यन्तयोगः)
load R1 saha 1
load R2 saha 5
R1 itaḥ R2 paryantayogaḥ  # R1 इतः R2 पर्यन्तयोगः — Sum 1+2+3+4+5 = 15

# Increment / Decrement
pluta R1                # प्लुत R1 — Increment
hrāsa R1                # ह्रास R1 — Decrement

# Stack operations
juṣa R1                 # जुष R1 — Push
gṛhṇa R2               # गृह्ण R2 — Pop

# Comparison
R1 tulya R2             # R1 तुल्य R2 — Compare

# Halt
virāma                  # विराम — Stop
```

### Python API

```python
from flux_san import FluxInterpreterSan, Vibhakti, Lakara, SamasaType

# Create interpreter
interp = FluxInterpreterSan()

# Execute Sanskrit NL
interp.execute_line("load R1 saha 42")
interp.execute_line("load R2 saha 8")
interp.execute_line("R1 guṇa R2")  # R0 = 336

# Work with vibhakti (case system)
from flux_san import Vibhakti, ScopeLevel
assert Vibhakti.SAMBODHANA.scope == ScopeLevel.INVOCATION

# Work with lakāra (execution modes)
from flux_san import Lakara, ExecutionMode
assert Lakara.ASIRLING.execution_mode == ExecutionMode.FORCED

# Work with samāsa (compounds)
from flux_san import SamasaParser, SamasaType
compound = SamasaParser.parse("rāśiyogaḥ")  # → sum compound
```

## व्याकरणस्य सम्बन्धः (Grammar Mapping)

### Why Sanskrit?

Pāṇini's Aṣṭādhyāyī (c. 4th century BCE) is a **formal generative grammar** with:
- **3,959 sūtras** (rules) operating on **1,700 pratyāhāras** (elements)
- **Anubandhas** (markers) that function like type annotations
- **Saṃjñās** (technical terms) that function like type names
- **Paribhāṣās** (meta-rules) that function like compiler passes

This makes Sanskrit grammar structurally equivalent to a type system / compiler pipeline — just expressed 2,400 years before computer science.

## अनुज्ञापत्रम् (License)

MIT
