"""
FLUX-san CLI — Sanskrit-first Command-Line Interface
======================================================

Commands:
  नमस्कार (namaskāra)   — Greeting / show banner
  निर्मा   (nirmā)       — Build / compile a program
  चालय   (cālaya)       — Execute a program
  विच्छेद  (viccheda)   — Analyze / disassemble
  संन्धि   (saṃdhi)      — Sandhi resolution
  विभक्ति  (vibhakti)    — Show case system table
  कालः     (kālaḥ)       — Show lakāra execution modes table
  समासः   (samāsaḥ)     — Show compound type table
  परीक्षा (parīkṣā)      — Run tests
"""

from __future__ import annotations

import sys
import argparse

from flux_san import __version__, __sanskrit_title__
from flux_san.vibhakti import VibhaktiValidator
from flux_san.lakara import LakaraDetector
from flux_san.samasa import SamasaParser
from flux_san.interpreter import FluxInterpreterSan


BANNER = r"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██╗      ██████╗ ██████╗║
║  ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██║     ██╔═══██╗██╔══██╗║
║  ██║     ██║   ██║██╔██╗ ██║██║   ██║███████╗██║     ██║   ██║██████╔╝║
║  ██║     ██║   ██║██║╚██╗██║██║   ██║╚════██║██║     ██║   ██║██╔═══╝ ║
║  ╚██████╗╚██████╔╝██║ ╚████║╚██████╔╝███████║███████╗╚██████╔╝██║     ║
║   ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚══════╝ ╚═════╝ ╚═╝     ║
║                                                                      ║
║   प्रवाहिनी — भाषा सार्वभौमिक निष्पादनम्                                 ║
║   Pravāhinī — Bhāṣā Sārvabhaumika Niṣpādanam                        ║
║   Fluent Language Universal Execution — Sanskrit-first               ║
║                                                                      ║
║   Pāṇinian Grammar = Type System                                     ║
║   3,959 Rules  •  1,700 Elements  •  8 Cases  •  8 Modes            ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""


def cmd_namaskara(args: argparse.Namespace) -> None:
    """Show greeting and banner."""
    print(BANNER)
    print(f"  Version: {__version__}")
    print(f"  Sanskrit Title: {__sanskrit_title__}")
    print()
    print("  अस्तौ माङ्गलम् — auspicious beginning")
    print("  Pāṇini's Aṣṭādhyāyī as formal type system")
    print()
    print("  Available commands:")
    print("    namaskāra  (नमस्कार)    — Show this banner")
    print("    nirmā      (निर्मा)      — Build / compile program")
    print("    cālaya     (चालय)      — Execute program")
    print("    viccheda   (विच्छेद)    — Analyze / show info")
    print("    saṃdhi     (संन्धि)     — Resolve sandhi")
    print("    vibhakti   (विभक्ति)    — Show case system")
    print("    kālaḥ      (कालः)       — Show execution modes")
    print("    samāsaḥ    (समासः)     — Show compound types")
    print("    parīkṣā    (परीक्षा)   — Run tests")
    print("    REPL       (interactive) — Enter interactive mode")
    print()


def cmd_nirma(args: argparse.Namespace) -> None:
    """Build / compile a Sanskrit program."""
    print(f"  निर्मा — Building program: {args.file}")
    interp = FluxInterpreterSan(trace=True)
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
        result = interp.execute_program(source)
        if result.success:
            print(f"  ✓ सिद्धम् — Build successful (cycles: {result.cycles})")
        else:
            print(f"  ✗ दोषः — Build failed: {result.error}")
    except FileNotFoundError:
        print(f"  ✗ दोषः — File not found: {args.file}")


def cmd_calaya(args: argparse.Namespace) -> None:
    """Execute a Sanskrit program."""
    print(f"  चालय — Executing program: {args.file}")
    interp = FluxInterpreterSan(trace=args.trace)
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()

        if args.mode == "program":
            result = interp.execute_program(source)
        else:
            results = interp.execute_lines(source)
            result = results[-1] if results else None

        if result and result.success:
            print(f"  ✓ सिद्धम् — Execution complete")
            print(f"  Result (R0): {result.result}")
            print(f"  Cycles: {result.cycles}")
            if args.show_registers:
                print(f"  Registers: {result.registers[:8]}")  # First 8
        elif result:
            print(f"  ✗ दोषः — {result.error}")
    except FileNotFoundError:
        print(f"  ✗ दोषः — File not found: {args.file}")


def cmd_viccheda(args: argparse.Namespace) -> None:
    """Analyze / show info."""
    if args.what == "vibhakti":
        print(VibhaktiValidator.all_cases_table())
    elif args.what == "lakara":
        print(LakaraDetector.all_lakaras_table())
    elif args.what == "samasa":
        print(SamasaParser.all_samasa_table())
    elif args.what == "banner":
        print(BANNER)
    else:
        print(f"  अज्ञातम् — Unknown analysis target: {args.what}")


def cmd_sandhi(args: argparse.Namespace) -> None:
    """Resolve sandhi for a compound word."""
    compound = args.word
    parts = SamasaParser.split_sandhi_simple(compound)
    print(f"  संन्धिविच्छेदः — Sandhi resolution for: {compound}")
    print(f"  Components: {parts}")

    # Also try compound parsing
    parsed = SamasaParser.parse(compound)
    if parsed:
        print(f"  Samāsa type: {parsed.samasa_type.iast} ({parsed.samasa_type.devanagari})")
        print(f"  Meaning: {parsed.meaning}")
        print(f"  Type: {parsed.type_expr}")


def cmd_vibhakti_table(args: argparse.Namespace) -> None:
    """Show the vibhakti case system table."""
    print(VibhaktiValidator.all_cases_table())


def cmd_kala_table(args: argparse.Namespace) -> None:
    """Show the lakāra execution modes table."""
    print(LakaraDetector.all_lakaras_table())


def cmd_samasa_table(args: argparse.Namespace) -> None:
    """Show the samāsa compound type table."""
    print(SamasaParser.all_samasa_table())


def cmd_pariksha(args: argparse.Namespace) -> None:
    """Run tests."""
    import subprocess
    print("  परीक्षा — Running tests...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd="/home/z/my-project/repos/flux-runtime-san",
        capture_output=False,
    )
    sys.exit(result.returncode)


def repl_mode() -> None:
    """Interactive REPL in Sanskrit."""
    print(BANNER)
    print("  प्रवाहिनी REPL — Interactive Mode")
    print("  Type Sanskrit commands in IAST. 'niṣkrama' to exit.")
    print("  Type 'sahāya' for help.\n")

    interp = FluxInterpreterSan(trace=False)

    while True:
        try:
            line = input("प्रवाहिनी> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  विराम — Halted. नमस्ते!")
            break

        if not line:
            continue

        if line in ("niṣkrama", "exit", "quit", "विराम"):
            print("  विराम — Halted. नमस्ते!")
            break

        if line in ("sahāya", "help", "साहाय्यम्"):
            print("\n  Available patterns (IAST):")
            print("    load R1 saha 42          — Load 42 into R1")
            print("    load R2 saha 7           — Load 7 into R2")
            print("    gaṇaya R1 pluta R2       — Add R1 + R2 → R0")
            print("    R1 guṇa R2               — Multiply R1 * R2 → R0")
            print("    R1 śoṣa R2               — Subtract R1 - R2 → R0")
            print("    R1 bhāj R2               — Divide R1 / R2 → R0")
            print("    R1 itaḥ R5 paryantayogaḥ — Sum from R1 to R5")
            print("    R1 tulya R2              — Compare R1, R2")
            print("    pluta R1                 — Increment R1")
            print("    hrāsa R1                 — Decrement R1")
            print("    juṣa R1                  — Push R1 to stack")
            print("    gṛhṇa R1                — Pop from stack to R1")
            print("    darśaya R0               — Print R0")
            print("    virāma                   — Halt")
            print("    saṃdhi devāśva           — Sandhi split")
            print("    vibhakti ramasya         — Detect case")
            print("    Registers are R0-R63\n")
            continue

        if line == "registers" or line == "अवस्था":
            regs = interp.registers
            print(f"  R0={regs[0]} R1={regs[1]} R2={regs[2]} R3={regs[3]} "
                  f"R4={regs[4]} R5={regs[5]} R6={regs[6]} R7={regs[7]}")
            continue

        result = interp.execute_line(line)

        if result.success:
            if result.halted:
                print(f"  विराम — Halted. R0={result.result}")
            else:
                r0 = interp.registers[0]
                print(f"  सिद्धम् — R0={r0}")
        else:
            print(f"  दोषः — {result.error}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="flux-san",
        description="प्रवाहिनी — FLUX Sanskrit-first Natural Language Runtime",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command (संज्ञा)")

    # namaskāra
    sub = subparsers.add_parser("namaskara", aliases=["namaskāra", "नमस्कार"],
                                 help="Show greeting banner (नमस्कार)")
    sub.set_defaults(func=cmd_namaskara)

    # nirmā
    sub = subparsers.add_parser("nirma", aliases=["nirmā", "निर्मा"],
                                 help="Build/compile program (निर्मा)")
    sub.add_argument("file", help="Source file path")
    sub.set_defaults(func=cmd_nirma)

    # cālaya
    sub = subparsers.add_parser("calaya", aliases=["cālaya", "चालय"],
                                 help="Execute program (चालय)")
    sub.add_argument("file", help="Source file path")
    sub.add_argument("--trace", action="store_true", help="Enable trace")
    sub.add_argument("--show-registers", action="store_true", help="Show register state")
    sub.add_argument("--mode", choices=["program", "lines"], default="program",
                     help="Execution mode: program (single bytecode) or lines")
    sub.set_defaults(func=cmd_calaya)

    # viccheda
    sub = subparsers.add_parser("viccheda", aliases=["viccheda", "विच्छेद"],
                                 help="Analyze/show info (विच्छेद)")
    sub.add_argument("what", choices=["vibhakti", "lakara", "samasa", "banner"],
                     help="What to analyze")
    sub.set_defaults(func=cmd_viccheda)

    # saṃdhi
    sub = subparsers.add_parser("sandhi", aliases=["saṃdhi", "संन्धि"],
                                 help="Resolve sandhi (संन्धिविच्छेदः)")
    sub.add_argument("word", help="Compound word to resolve")
    sub.set_defaults(func=cmd_sandhi)

    # vibhakti
    sub = subparsers.add_parser("vibhakti", aliases=["विभक्ति"],
                                 help="Show case system table (विभक्तिः)")
    sub.set_defaults(func=cmd_vibhakti_table)

    # kālaḥ
    sub = subparsers.add_parser("kala", aliases=["kālaḥ", "कालः"],
                                 help="Show execution modes table (कालः)")
    sub.set_defaults(func=cmd_kala_table)

    # samāsaḥ
    sub = subparsers.add_parser("samasa", aliases=["samāsaḥ", "समासः"],
                                 help="Show compound type table (समासः)")
    sub.set_defaults(func=cmd_samasa_table)

    # parīkṣā
    sub = subparsers.add_parser("pariksha", aliases=["parīkṣā", "परीक्षा"],
                                 help="Run tests (परीक्षा)")
    sub.set_defaults(func=cmd_pariksha)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for flux-san CLI."""
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]

    # No arguments → REPL mode
    if not argv:
        repl_mode()
        return 0

    args = parser.parse_args(argv)

    if hasattr(args, "func"):
        args.func(args)
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
