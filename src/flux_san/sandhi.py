"""
Sandhi — Phonological Combination Rules as Syntax
===================================================

Sanskrit's sandhi (phonological combination) is not mere grammar — in the
FLUX runtime, sandhi IS the tokenizer.  When two morphemes meet at a word
boundary, the phonological transformation that occurs determines the
syntactic relationship between them, which in turn determines the bytecode
that should be emitted.

Pāṇini codified sandhi in the Aṣṭādhyāyī sūtras:
  "Coalescence of two sounds at a word boundary" (saṃhitā)

The three major categories of sandhi in FLUX:

  1. Vowel Sandhi (स्वरसन्धिḥ):
     When two vowels meet at a word boundary, they merge into a single
     (usually guṇa or vṛddhi) vowel.  In FLUX, this produces CONTROL FLOW
     MERGE — two code paths fuse into one.

     Rules:
       a + a → ā      (Identity → Persistence)
       a + i → e       (Identity + Near → Close)
       a + u → o       (Identity + Remote → Far)
       i + a → ya      (Near + Identity → Junction)
       u + a → va      (Remote + Identity → Junction)
       ā + ā → ā       ( Persistence × 2 → Persistence)
       i + i → ī       (Near × 2 → Intensified Near)
       u + u → ū       (Remote × 2 → Intensified Remote)

  2. Visarga Sandhi (विसर्गसन्धिः):
     The visarga (ः) is a word-final breath release that transforms
     depending on the following sound.  In FLUX, visarga sandhi acts
     as a LOOP TERMINATOR or BOUNDARY MARKER.

     Rules:
       ḥ → s before voiced consonants  (soft termination)
       ḥ → ḥ before vowels             (continuation marker)
       ḥ → o before voiced stops        (open boundary)
       aḥ → aḥ (retained) before spaces (hard stop / HALT)

  3. Consonant Sandhi (व्यञ्जनसन्धिः):
     When two consonants meet, they may combine (saṃyoga), or the first
     may undergo nasalization.  In FLUX, this produces MULTI-REGISTER
     OPERATIONS — two independent instructions fuse into one compound op.

     Rules:
       k + ś → kṣ    (unvoiced velar + palatal → palatal affricate)
       t + th → tth  (dental + dental aspirate → geminate)
       n + j → ñj    (nasal + palatal → palatal nasal + palatal)

From Pāṇini's Aṣṭādhyāyī:
  saṃhitā sandhi-viccheda-prakaraṇam
  "The chapter on sandhi combination and splitting"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from flux_san.vm import Opcode


# ---------------------------------------------------------------------------
# Sandhi type classification
# ---------------------------------------------------------------------------

class SandhiType(IntEnum):
    """The categories of phonological combination."""
    VOWEL       = 1   # स्वरसन्धिः   — vowel combination
    VISARGA     = 2   # विसर्गसन्धिः  — visarga transformation
    CONSONANT   = 3   # व्यञ्जनसन्धिः  — consonant combination
    EXTERNAL    = 4   # बाह्यसन्धिः   — word-boundary (statement separation)
    INTERNAL    = 5   # आन्तरसन्धिः   — intra-word (opcode selection)
    NONE        = 0   # असन्धिः       — no sandhi applicable


class SandhiEffect(IntEnum):
    """What the sandhi transformation means at the bytecode level."""
    MERGE       = 1   # Two paths merge → JMP merge
    TERMINATE   = 2   # Loop/boundary end → HALT / JNZ → loop start
    MULTI_OP    = 3   # Two instructions fuse → compound op
    STATEMENT_SEP = 4  # Word boundary → statement separator (NOP or next)
    OPCODE_CHANGE = 5  # Intra-word change → different opcode variant
    NOOP        = 0   # No bytecode effect


# ---------------------------------------------------------------------------
# Individual sandhi rule
# ---------------------------------------------------------------------------

@dataclass
class SandhiRule:
    """A single sandhi transformation rule.

    Attributes:
        name: Human-readable rule name.
        sanskrit_name: Rule name in Devanāgarī.
        pattern: Regex pattern matching the input sequence.
        replacement: Replacement string or callable.
        type: Category of sandhi.
        effect: Bytecode-level effect.
        description: Explanation of the phonological and semantic change.
        bytecode_hint: Optional opcode hint for the compiler.
    """
    name: str
    sanskrit_name: str
    pattern: re.Pattern
    replacement: str | Any
    type: SandhiType
    effect: SandhiEffect
    description: str = ""
    bytecode_hint: Opcode | None = None
    priority: int = 0  # Higher = applied first

    def apply(self, text: str) -> str:
        """Apply this sandhi rule to *text*."""
        if callable(self.replacement):
            return self.replacement(text)
        return self.pattern.sub(self.replacement, text)

    def matches(self, text: str) -> bool:
        """Check if this rule applies to *text*."""
        return bool(self.pattern.search(text))

    def __repr__(self) -> str:
        return f"SandhiRule({self.name}, {self.type.name}, {self.effect.name})"


# ---------------------------------------------------------------------------
# Token — a unit produced by sandhi tokenization
# ---------------------------------------------------------------------------

@dataclass
class SandhiToken:
    """A token produced by sandhi-based tokenization of Sanskrit text.

    Each token carries:
      - text: the original (possibly sandhi-combined) text
      - stem: the resolved stem/root before sandhi
      - type: morphological category (verb, noun, particle, etc.)
      - sandhi_applied: the type of sandhi that produced this token
      - bytecode_hint: suggested opcode for this token
      - position: character offset in the source text
    """
    text: str
    stem: str = ""
    type: str = "unknown"  # verb, noun, numeral, particle, operator
    sandhi_applied: SandhiType = SandhiType.NONE
    bytecode_hint: Opcode | None = None
    position: int = 0
    children: list[SandhiToken] = field(default_factory=list)

    @property
    def is_compound(self) -> bool:
        """True if this token is a sandhi compound of sub-tokens."""
        return len(self.children) > 0

    @property
    def is_terminal(self) -> bool:
        """True if this token terminates a statement (visarga/visarga-sandhi)."""
        return self.sandhi_applied == SandhiType.VISARGA

    def __repr__(self) -> str:
        return (
            f"SandhiToken({self.text!r}, stem={self.stem!r}, "
            f"type={self.type!r}, sandhi={self.sandhi_applied.name})"
        )


# ---------------------------------------------------------------------------
# Sandhi engine
# ---------------------------------------------------------------------------

class SandhiEngine:
    """Sanskrit sandhi processing engine for FLUX compilation.

    The SandhiEngine handles both JOINING (applying sandhi rules to combine
    morphemes) and SPLITTING (reversing sandhi to recover original forms).
    In the FLUX compilation pipeline:
      1. Source text is first tokenized by external sandhi (word boundaries)
      2. Each word is then processed by internal sandhi (intra-word)
      3. The sandhi type determines the bytecode instruction to emit

    Usage::

        engine = SandhiEngine()

        # Apply sandhi joining
        result = engine.join("deva", "aśva")
        # → "devāśva" (vowel sandhi: a + a → ā)

        # Split sandhi
        parts = engine.split("devāśva")
        # → ["deva", "aśva"]

        # Tokenize a Sanskrit sentence
        tokens = engine.tokenize("devāśvaḥ gacchati")
        # → [SandhiToken("devāśvaḥ"), SandhiToken("gacchati")]

        # Full compilation pipeline
        tokens = engine.tokenize_source("rāmaḥ gacchati. viśvāsaḥ")
    """

    def __init__(self):
        self._vowel_rules = self._build_vowel_rules()
        self._visarga_rules = self._build_visarga_rules()
        self._consonant_rules = self._build_consonant_rules()
        self._external_rules = self._build_external_rules()
        self._all_rules = (
            self._external_rules
            + self._vowel_rules
            + self._visarga_rules
            + self._consonant_rules
        )

    # ---- Rule builders ----

    @staticmethod
    def _build_vowel_rules() -> list[SandhiRule]:
        """Build vowel sandhi (स्वरसन्धिः) rules.

        Vowel sandhi occurs when two vowels meet at a word boundary.
        In IAST notation, these are the standard Pāṇinian rules.
        """
        rules = [
            # a + a → ā (guṇa sandhi)
            SandhiRule(
                name="a+a_to_ā",
                sanskrit_name="अ+अ→आ",
                pattern=re.compile(r"a(?=a)", re.IGNORECASE),
                replacement="ā",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MERGE,
                description="When a meets a → ā (identity persists)",
                bytecode_hint=Opcode.MOV,
                priority=10,
            ),
            # a + i → e (guṇa sandhi)
            SandhiRule(
                name="a+i_to_e",
                sanskrit_name="अ+इ→ए",
                pattern=re.compile(r"a(?=i)", re.IGNORECASE),
                replacement="e",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MERGE,
                description="When a meets i → e (identity absorbs near)",
                bytecode_hint=Opcode.JZ,
                priority=10,
            ),
            # a + u → o
            SandhiRule(
                name="a+u_to_o",
                sanskrit_name="अ+उ→ओ",
                pattern=re.compile(r"a(?=u)", re.IGNORECASE),
                replacement="o",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MERGE,
                description="When a meets u → o (identity absorbs remote)",
                bytecode_hint=Opcode.JMP,
                priority=10,
            ),
            # a + ṛ → ar (guṇa of ṛ)
            SandhiRule(
                name="a+ṛ_to_ar",
                sanskrit_name="अ+ऋ→अर्",
                pattern=re.compile(r"a(?=ṛ)", re.IGNORECASE),
                replacement="ar",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MERGE,
                description="When a meets ṛ → ar (identity absorbs r-hot)",
                bytecode_hint=Opcode.CALL,
                priority=10,
            ),
            # i + a → ya (ya-vṛddhi)
            SandhiRule(
                name="i+a_to_ya",
                sanskrit_name="इ+अ→य",
                pattern=re.compile(r"i(?=a)", re.IGNORECASE),
                replacement="ya",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MULTI_OP,
                description="When i meets a → ya (junction form)",
                bytecode_hint=Opcode.IADD,
                priority=10,
            ),
            # u + a → va (va-vṛddhi)
            SandhiRule(
                name="u+a_to_va",
                sanskrit_name="उ+अ→व",
                pattern=re.compile(r"u(?=a)", re.IGNORECASE),
                replacement="va",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MULTI_OP,
                description="When u meets a → va (junction form)",
                bytecode_hint=Opcode.ISUB,
                priority=10,
            ),
            # i + i → ī (vṛddhi sandhi)
            SandhiRule(
                name="i+i_to_ī",
                sanskrit_name="इ+इ→ई",
                pattern=re.compile(r"i(?=i)", re.IGNORECASE),
                replacement="ī",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MERGE,
                description="When i meets i → ī (intensified near)",
                bytecode_hint=Opcode.INC,
                priority=10,
            ),
            # u + u → ū (vṛddhi sandhi)
            SandhiRule(
                name="u+u_to_ū",
                sanskrit_name="उ+उ→ऊ",
                pattern=re.compile(r"u(?=u)", re.IGNORECASE),
                replacement="ū",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MERGE,
                description="When u meets u → ū (intensified remote)",
                bytecode_hint=Opcode.DEC,
                priority=10,
            ),
            # r̄ + a → ra (retroflex + a)
            SandhiRule(
                name="r+a_to_ra",
                sanskrit_name="ऋ+अ→र",
                pattern=re.compile(r"ṛ(?=a)", re.IGNORECASE),
                replacement="ra",
                type=SandhiType.VOWEL,
                effect=SandhiEffect.MULTI_OP,
                description="When ṛ meets a → ra",
                bytecode_hint=Opcode.IMUL,
                priority=5,
            ),
        ]
        return rules

    @staticmethod
    def _build_visarga_rules() -> list[SandhiRule]:
        """Build visarga sandhi (विसर्गसन्धिः) rules.

        The visarga (ḥ / ः) is a word-final breath marker that transforms
        based on the following sound.  In FLUX, visarga acts as a statement
        terminator, loop boundary marker, or region delimiter.
        """
        rules = [
            # Visarga before voiced consonant → s
            SandhiRule(
                name="visarga_to_s_voiced",
                sanskrit_name="ः→स् (before voiced)",
                pattern=re.compile(r"ḥ(?=[gjḍdb])"),
                replacement="s",
                type=SandhiType.VISARGA,
                effect=SandhiEffect.TERMINATE,
                description="Visarga before voiced → soft termination (s)",
                bytecode_hint=Opcode.JZ,
                priority=20,
            ),
            # Visarga before voiceless consonant → ś
            SandhiRule(
                name="visarga_to_ś_voiceless",
                sanskrit_name="ः→श् (before voiceless)",
                pattern=re.compile(r"ḥ(?=[kctp])"),
                replacement="ś",
                type=SandhiType.VISARGA,
                effect=SandhiEffect.TERMINATE,
                description="Visarga before voiceless → ś (loop terminator)",
                bytecode_hint=Opcode.JNZ,
                priority=20,
            ),
            # Visarga before vowel → o
            SandhiRule(
                name="visarga_to_o_vowel",
                sanskrit_name="ः→ओ (before vowel)",
                pattern=re.compile(r"aḥ(?=[aeiou])"),
                replacement="o",
                type=SandhiType.VISARGA,
                effect=SandhiEffect.TERMINATE,
                description="aḥ before vowel → o (open boundary)",
                bytecode_hint=Opcode.JE,
                priority=20,
            ),
            # r̄-ending visarga → raḥ → ro before vowels
            SandhiRule(
                name="r_visarga_to_ro",
                sanskrit_name="र्-विसर्गः→रो",
                pattern=re.compile(r"rḥ(?=[aeiou])"),
                replacement="ro",
                type=SandhiType.VISARGA,
                effect=SandhiEffect.TERMINATE,
                description="rḥ before vowel → ro",
                bytecode_hint=Opcode.JNE,
                priority=15,
            ),
            # Visarga at end of word / sentence → HALT signal
            SandhiRule(
                name="visarga_terminal",
                sanskrit_name="ः (terminal)",
                pattern=re.compile(r"ḥ\s*$"),
                replacement="ḥ",
                type=SandhiType.VISARGA,
                effect=SandhiEffect.TERMINATE,
                description="Terminal visarga → statement terminator (HALT)",
                bytecode_hint=Opcode.HALT,
                priority=25,
            ),
        ]
        return rules

    @staticmethod
    def _build_consonant_rules() -> list[SandhiRule]:
        """Build consonant sandhi (व्यञ्जनसन्धिः) rules.

        Consonant sandhi occurs when consonants combine at word boundaries.
        In FLUX, this produces compound/multi-register operations.
        """
        rules = [
            # k + ś → kṣ (unvoiced velar + palatal)
            SandhiRule(
                name="k+ś_to_kṣ",
                sanskrit_name="क्+श्→क्ष्",
                pattern=re.compile(r"k(?=ś)"),
                replacement="kṣ",
                type=SandhiType.CONSONANT,
                effect=SandhiEffect.MULTI_OP,
                description="k before ś → kṣ (compound palatal affricate)",
                bytecode_hint=Opcode.IMUL,
                priority=10,
            ),
            # t + th → tth (dental gemination)
            SandhiRule(
                name="t+th_to_tth",
                sanskrit_name="त्+त्→त्त्",
                pattern=re.compile(r"t(?=th)"),
                replacement="tth",
                type=SandhiType.CONSONANT,
                effect=SandhiEffect.MULTI_OP,
                description="t before th → tth (geminate → double operation)",
                bytecode_hint=Opcode.IADD,
                priority=10,
            ),
            # n + j → ñj (nasal + palatal)
            SandhiRule(
                name="n+j_to_ñj",
                sanskrit_name="न्+ज्→ञ्ज्",
                pattern=re.compile(r"n(?=j)"),
                replacement="ñj",
                type=SandhiType.CONSONANT,
                effect=SandhiEffect.MULTI_OP,
                description="n before j → ñj (nasal palatal cluster)",
                bytecode_hint=Opcode.IADD,
                priority=10,
            ),
            # n + s → ñs (nasal + sibilant at word boundary)
            SandhiRule(
                name="n+s_to_ñs",
                sanskrit_name="न्+स्→ञ्स्",
                pattern=re.compile(r"n(?=s)"),
                replacement="ñs",
                type=SandhiType.CONSONANT,
                effect=SandhiEffect.MULTI_OP,
                description="n before s → ñs (nasal sibilant)",
                bytecode_hint=Opcode.ISUB,
                priority=10,
            ),
            # c + ch → cch (palatal gemination)
            SandhiRule(
                name="c+ch_to_cch",
                sanskrit_name="च्+छ्→च्छ्",
                pattern=re.compile(r"c(?=ch)"),
                replacement="cch",
                type=SandhiType.CONSONANT,
                effect=SandhiEffect.MULTI_OP,
                description="c before ch → cch (palatal geminate)",
                bytecode_hint=Opcode.IMUL,
                priority=8,
            ),
            # Final s → ḥ between words (retroflex sibilant)
            SandhiRule(
                name="s_final_to_visarga",
                sanskrit_name="स्→ः (word-final)",
                pattern=re.compile(r"s(?=\s|$)"),
                replacement="ḥ",
                type=SandhiType.CONSONANT,
                effect=SandhiEffect.TERMINATE,
                description="Final s → visarga (word boundary)",
                bytecode_hint=Opcode.HALT,
                priority=5,
            ),
        ]
        return rules

    @staticmethod
    def _build_external_rules() -> list[SandhiRule]:
        """Build external sandhi (बाह्यसन्धिः) rules — word-boundary markers.

        External sandhi determines STATEMENT SEPARATION in the FLUX source.
        Spaces, punctuation, and visarga at word boundaries signal the end
        of one statement and the beginning of another.
        """
        rules = [
            # Period / danda (।) → statement terminator
            SandhiRule(
                name="danda_terminator",
                sanskrit_name="। (दण्डः)",
                pattern=re.compile(r"[।.]"),
                replacement=" HALT_TOKEN ",
                type=SandhiType.EXTERNAL,
                effect=SandhiEffect.STATEMENT_SEP,
                description="Danda (।) → statement terminator → HALT",
                bytecode_hint=Opcode.HALT,
                priority=30,
            ),
            # Double danda (॥) → paragraph / block separator
            SandhiRule(
                name="double_danda",
                sanskrit_name="॥ (द्विदण्डः)",
                pattern=re.compile(r"॥"),
                replacement=" BLOCK_SEP ",
                type=SandhiType.EXTERNAL,
                effect=SandhiEffect.STATEMENT_SEP,
                description="Double danda (॥) → block separator",
                bytecode_hint=Opcode.NOP,
                priority=30,
            ),
            # Comma → NOP separator
            SandhiRule(
                name="comma_separator",
                sanskrit_name=",(पृथक्)",
                pattern=re.compile(r","),
                replacement=" NOP_SEP ",
                type=SandhiType.EXTERNAL,
                effect=SandhiEffect.STATEMENT_SEP,
                description="Comma → NOP separator between clauses",
                bytecode_hint=Opcode.NOP,
                priority=25,
            ),
        ]
        return rules

    # ---- Sandhi joining (apply sandhi to combine morphemes) ----

    def join(self, word1: str, word2: str) -> str:
        """Apply external sandhi to join two words.

        Tries all sandhi rules in priority order and returns the first
        successful combination.  Falls back to simple concatenation.

        Args:
            word1: First word (left morpheme).
            word2: Second word (right morpheme).

        Returns:
            The sandhi-combined form.
        """
        combined = word1 + word2

        # Try vowel sandhi between word1's last char and word2's first char
        for rule in self._vowel_rules:
            if rule.pattern.search(combined):
                result = rule.apply(combined)
                if result != combined:
                    return result

        # Try visarga sandhi on word1's ending + word2's start
        for rule in self._visarga_rules:
            test = word1 + word2
            if rule.pattern.search(test):
                result = rule.apply(test)
                if result != test:
                    return result

        # Try consonant sandhi
        for rule in self._consonant_rules:
            if rule.pattern.search(combined):
                result = rule.apply(combined)
                if result != combined:
                    return result

        return combined

    # ---- Sandhi splitting (reverse sandhi to recover morphemes) ----

    def split(self, word: str) -> list[str]:
        """Reverse sandhi to recover original morpheme components.

        This is a heuristic split — full sandhi reversal requires the
        complete Pāṇinian rule system.  Our implementation handles the
        most common patterns.

        Only multi-character digraph sandhi patterns are applied during
        splitting to avoid infinite loops from single-character matches.

        Args:
            word: A (possibly sandhi-combined) word.

        Returns:
            List of original morpheme components.
        """
        if not word:
            return []

        # Known split patterns: combined → [part1, part2]
        # Only multi-character patterns to avoid infinite loops
        _SPLIT_PATTERNS: list[tuple[str, list[str]]] = [
            # Vowel sandhi reversals (long vowels → two short vowels)
            ("ā",  ["a", "a"]),        # a + a → ā
            ("ī",  ["i", "i"]),        # i + i → ī
            ("ū",  ["u", "u"]),        # u + u → ū
            ("ai", ["a", "i"]),         # a + i → e (sometimes written ai)
            ("au", ["a", "u"]),         # a + u → o (sometimes written au)
            ("ya", ["i", "a"]),         # i + a → ya (y-vṛddhi)
            ("va", ["u", "a"]),         # u + a → va (v-vṛddhi)
            ("ar", ["a", "ṛ"]),         # a + ṛ → ar
            ("ra", ["ṛ", "a"]),         # ṛ + a → ra
            # Consonant sandhi reversals
            ("kṣ", ["k", "ś"]),        # k + ś → kṣ
            ("ñj", ["ñ", "j"]),         # ñ + j → ñj
            ("tth", ["t", "th"]),       # t + th → tth
            ("cch", ["c", "ch"]),       # c + ch → cch
            ("ñs", ["ñ", "s"]),         # ñ + s → ñs
            # Visarga sandhi reversals
            ("ass", ["aḥ", ""]),       # aḥ → ass (before sibilant)
        ]

        results: list[str] = []
        visited: set[str] = set()
        queue: list[str] = [word]
        max_iterations = 200

        while queue and len(results) < max_iterations:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            split_applied = False
            # Try each split pattern (sorted by length desc for longest match)
            for pattern, parts in sorted(_SPLIT_PATTERNS, key=lambda x: -len(x[0])):
                idx = current.find(pattern)
                if idx > 0 and idx < len(current) - 1:
                    before = current[:idx]
                    after = current[idx + len(pattern):]
                    for p in parts:
                        if p:
                            candidate = before + p + after
                            if candidate not in visited and candidate != current:
                                queue.append(candidate)
                                split_applied = True

            if not split_applied:
                # No more splits possible — this is a terminal result
                if current != word:
                    results.append(current)

        return results if results else [word]

    # ---- Tokenization ----

    def tokenize(self, text: str) -> list[SandhiToken]:
        """Tokenize a Sanskrit text string using sandhi rules.

        The tokenizer:
          1. Splits on whitespace and external separators (।, ,, ॥)
          2. Classifies each token by morphological type
          3. Detects sandhi type for each token
          4. Assigns bytecode hints based on sandhi effects

        Args:
            text: Sanskrit text in IAST transliteration.

        Returns:
            List of SandhiTokens with type and bytecode hints.
        """
        tokens: list[SandhiToken] = []

        # Normalize: handle Devanāgarī punctuation → IAST
        normalized = text
        normalized = normalized.replace("।", " । ")
        normalized = normalized.replace("॥", " ॥ ")

        # Split on whitespace
        raw_words = normalized.split()
        position = 0

        for raw in raw_words:
            if not raw:
                continue

            # Check for punctuation tokens
            if raw in ("।", "HALT_TOKEN"):
                tokens.append(SandhiToken(
                    text="।",
                    stem="",
                    type="terminator",
                    sandhi_applied=SandhiType.VISARGA,
                    bytecode_hint=Opcode.HALT,
                    position=position,
                ))
                position += len(raw) + 1
                continue

            if raw in ("॥", "BLOCK_SEP"):
                tokens.append(SandhiToken(
                    text="॥",
                    stem="",
                    type="block_sep",
                    sandhi_applied=SandhiType.EXTERNAL,
                    bytecode_hint=Opcode.NOP,
                    position=position,
                ))
                position += len(raw) + 1
                continue

            if raw == "NOP_SEP":
                tokens.append(SandhiToken(
                    text=",",
                    stem="",
                    type="separator",
                    sandhi_applied=SandhiType.EXTERNAL,
                    bytecode_hint=Opcode.NOP,
                    position=position,
                ))
                position += len(raw) + 1
                continue

            # Determine sandhi type and bytecode hint
            sandhi_type = SandhiType.NONE
            hint: Opcode | None = None
            token_type = self._classify_token(raw)

            # Check visarga endings
            if raw.endswith("ḥ") or raw.endswith("ः"):
                sandhi_type = SandhiType.VISARGA
                hint = Opcode.HALT
            else:
                # Check for vowel sandhi indicators
                for rule in self._vowel_rules:
                    if rule.matches(raw):
                        sandhi_type = SandhiType.VOWEL
                        hint = rule.bytecode_hint
                        break

                # Check for consonant sandhi indicators
                if sandhi_type == SandhiType.NONE:
                    for rule in self._consonant_rules:
                        if rule.matches(raw):
                            sandhi_type = SandhiType.CONSONANT
                            hint = rule.bytecode_hint
                            break

            # If no sandhi detected, try to determine type from form
            if hint is None:
                hint = self._infer_opcode(raw, token_type)

            tokens.append(SandhiToken(
                text=raw,
                stem=self._resolve_stem(raw),
                type=token_type,
                sandhi_applied=sandhi_type,
                bytecode_hint=hint,
                position=position,
            ))
            position += len(raw) + 1

        return tokens

    def tokenize_source(self, source: str) -> list[SandhiToken]:
        """Tokenize a multi-line Sanskrit source program.

        Handles:
          - Line comments (starting with # or //)
          - Blank lines
          - Multi-statement lines

        Args:
            source: Multi-line Sanskrit FLUX source code.

        Returns:
            List of SandhiTokens for all non-comment, non-blank content.
        """
        tokens: list[SandhiToken] = []
        position = 0

        for line in source.split("\n"):
            line = line.strip()

            # Skip comments and blank lines
            if not line or line.startswith("#") or line.startswith("//"):
                position += len(line) + 1
                continue

            # Tokenize the line
            line_tokens = self.tokenize(line)
            for t in line_tokens:
                t.position += position
                tokens.append(t)

            position += len(line) + 1

        return tokens

    # ---- Helpers ----

    @staticmethod
    def _classify_token(word: str) -> str:
        """Classify a token by morphological type.

        Categories:
          - verb: ends with verbal conjugation marker
          - noun: ends with nominal declension marker
          - numeral: matches Sanskrit number word
          - operator: matches known operator term
          - register: matches register pattern (R0–R63)
          - particle: other
        """
        # Register pattern
        if re.match(r"^[Rr]\d+$", word):
            return "register"

        # Numerals (Sanskrit number words)
        _NUMERALS = {
            "śūnyam", "ekam", "dvi", "tri", "catur", "pañca",
            "ṣaṭ", "sapta", "aṣṭa", "nava", "daśa",
            "viṃśati", "triṃśat", "śata", "sahasra",
        }
        if word.lower() in _NUMERALS or re.match(r"^-?\d+$", word):
            return "numeral"

        # Verbs — common verbal endings (laṭ present)
        _VERB_ENDINGS = [
            "ti", "tasi", "anti", "te", "atae", "ante",
            "mi", "vas", "mas", "thāḥ", "dhvam",
            "tām", "yāt", "eta", "itum",
        ]
        for ending in _VERB_ENDINGS:
            if word.endswith(ending) and len(word) > len(ending):
                return "verb"

        # Known operator terms
        _OPERATORS = {
            "gaṇaya", "pluta", "guṇa", "śoṣa", "bhāj", "tulya",
            "paryantayogaḥ", "darśaya", "virāma", "load", "saṃdhi",
            "vibhakti", "hrāsa", "pluta", "juṣa", "gṛhṇa",
            "brūhi", "kathaya", "pṛccha", "niyujya", "prakaraṇaṃ",
            "viśvāsaṃ", "sthira", "sthāna",
        }
        if word.lower() in _OPERATORS:
            return "operator"

        # Nouns — vibhakti endings (case markers)
        _NOUN_ENDINGS = [
            "aḥ", "am", "eṇa", "āya", "āt", "asya", "e",
            "āni", "āḥ", "ām", "iḥ", "oḥ", "yaḥ",
        ]
        for ending in _NOUN_ENDINGS:
            if word.endswith(ending) and len(word) > len(ending):
                return "noun"

        return "particle"

    @staticmethod
    def _resolve_stem(word: str) -> str:
        """Attempt to resolve the stem/root of a word by stripping sandhi suffixes.

        This is a simplified stemmer — full morphological analysis requires
        the complete Pāṇinian system.
        """
        # Strip common nominal endings
        _STRIP_ENDINGS = [
            "aḥ", "am", "eṇa", "āya", "āt", "asya", "e", "āni",
            "āḥ", "ām", "iḥ", "oḥ", "yaḥ",
            # Verbal endings
            "ti", "tasi", "anti", "te", "atae", "ante",
            "yati", "ayati", "oti",
        ]
        for ending in sorted(_STRIP_ENDINGS, key=len, reverse=True):
            if word.endswith(ending) and len(word) > len(ending) + 1:
                return word[:-len(ending)]
        return word

    @staticmethod
    def _infer_opcode(word: str, token_type: str) -> Opcode | None:
        """Infer a bytecode hint from the token's form and type.

        Maps common Sanskrit operator terms to their FLUX opcodes.
        """
        _TERM_OPCODES: dict[str, Opcode] = {
            "gaṇaya":  Opcode.IADD,
            "pluta":   Opcode.IADD,
            "guṇa":    Opcode.IMUL,
            "śoṣa":    Opcode.ISUB,
            "bhāj":    Opcode.IDIV,
            "tulya":   Opcode.ICMP,
            "darśaya": Opcode.PRINT,
            "virāma":  Opcode.HALT,
            "juṣa":    Opcode.PUSH,
            "gṛhṇa":  Opcode.POP,
            "hrāsa":   Opcode.DEC,
            "brūhi":   Opcode.TELL,
            "kathaya": Opcode.TELL,
            "pṛccha":  Opcode.ASK,
            "niyujya": Opcode.DELEGATE,
            "load":    Opcode.MOVI,
            "sthira":  Opcode.STORE,
            "sthāna":  Opcode.MOVI,
        }

        lower = word.lower()
        if lower in _TERM_OPCODES:
            return _TERM_OPCODES[lower]

        # Type-based defaults
        if token_type == "verb":
            return Opcode.CALL
        if token_type == "register":
            return Opcode.MOV
        if token_type == "numeral":
            return Opcode.MOVI

        return None

    # ---- Display ----

    def rules_table(self) -> str:
        """Return a formatted table of all active sandhi rules."""
        lines = [
            "╔═══════════════════════════════════════════════════════════════════╗",
            "║  Sandhi Rules — FLUX-san Phonological Syntax System               ║",
            "║  सन्धिनियमाः — प्रवाहिनी ध्वनिव्याकरण-वाक्यविन्यासः                  ║",
            "╠══════════════════╦═══════════════╦═══════════╦═══════════════════╣",
            "║  Rule            ║ Sanskrit     ║ Type      ║ Bytecode Effect    ║",
            "╠══════════════════╬═══════════════╬═══════════╬═══════════════════╣",
        ]
        for rule in sorted(self._all_rules, key=lambda r: -r.priority):
            type_name = rule.type.name.capitalize()[:9]
            effect_name = rule.effect.name
            if rule.bytecode_hint:
                effect_name += f" ({rule.bytecode_hint.name})"
            lines.append(
                f"║  {rule.name:<16s} ║ {rule.sanskrit_name:<13s} "
                f"║ {type_name:<9s} ║ {effect_name:<17s} ║"
            )
        lines.append("╚══════════════════╩═══════════════╩═══════════╩═══════════════════╝")
        return "\n".join(lines)
