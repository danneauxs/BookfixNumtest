#!/usr/bin/env python3
"""
Headless command-line number processor for BookFix.

Reads a text file, applies rule-based number formatting for TTS,
writes an output file, and generates a change report.

Usage:
    python process_numbers.py <input_file> [--output <output_file>] [--report]

Examples:
    python process_numbers.py book.txt
    python process_numbers.py book.txt --output book_fixed.txt
    python process_numbers.py book.txt --report
"""

import sys
import argparse
from pathlib import Path

# Add numtest to path
sys.path.insert(0, str(Path(__file__).parent))

from rules_processor import RulesOnlyNumberProcessor
from paths import LOGS_DIR


def main():
    """Parse args and process the input file."""
    parser = argparse.ArgumentParser(
        description="Format numbers in text for TTS using rule-based classification"
    )
    parser.add_argument("input", help="Path to input text file")
    parser.add_argument(
        "--output",
        help="Path to output file (default: <input_stem>_numbered.txt in same directory)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed change report to console",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Open interactive review window before writing output",
    )
    parser.add_argument(
        "--ai-mode",
        choices=["rules_only", "rules_then_ai", "ai_only"],
        default="rules_only",
        help="AI mode: rules_only (default), rules_then_ai (AI on uncertain), ai_only (AI only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview proposals without writing output file",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    # Validate input file exists
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_stem(input_path.stem + "_numbered")

    # Read input
    try:
        text = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Input: {input_path}")
    print(f"  Size: {len(text)} characters")
    print(f"  Lines: {len(text.splitlines())}")

    # Helper function to write proposals report
    def write_proposals_report(proposals, input_path, dry_run=False):
        """Write proposals to a text file for preview."""
        header_suffix = " (DRY RUN)" if dry_run else ""
        report_path = LOGS_DIR / (input_path.stem + "_number_proposals.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"NUMBER FORMATTING PROPOSALS{header_suffix}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Input file:  {input_path}\n")
            f.write(f"Total proposals: {len(proposals)}\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write("DETAILED PROPOSALS\n")
            f.write("=" * 80 + "\n\n")

            for p in proposals:
                f.write(f"Line {p['line']:4d}\n")
                f.write(f"  Original:  {p['original']!r}\n")
                f.write(f"  Formatted: {p['formatted']!r}\n")
                f.write(f"  Type:      {p['type']}\n")
                f.write(f"  Rule:      {p['rule']}\n")
                f.write(f"  Sentence:  {p['full_sentence']}\n")
                f.write("\n")
        return report_path

    # Process
    try:
        processor = RulesOnlyNumberProcessor()

        if args.dry_run:
            # Dry-run: generate proposals and write to report, exit without output file
            lines, proposals = processor.propose(text, ai_mode=args.ai_mode)
            report_path = write_proposals_report(proposals, input_path, dry_run=True)

            print(f"Input: {input_path}")
            print(f"  Proposals: {len(proposals)}")
            print(f"\nReport: {report_path}")
            print("\nDone.")
            sys.exit(0)

        elif args.review:
            # Use propose() + review window + apply_proposals()
            from PyQt5.QtWidgets import QApplication

            lines, proposals = processor.propose(text, ai_mode=args.ai_mode)
            # Always write proposals report for preview
            write_proposals_report(proposals, input_path, dry_run=False)

            if proposals:
                # Launch review window
                app = QApplication.instance() or QApplication(sys.argv)
                from review_window import NumberReviewWindow

                review_window = NumberReviewWindow(text, proposals, processor)
                result = review_window.exec_()

                if result == review_window.Accepted:
                    reviewed_proposals = review_window.get_proposals()
                    output_text, changes = processor.apply_proposals(text, reviewed_proposals)
                else:
                    print("Review cancelled. No output written.")
                    sys.exit(0)
            else:
                output_text, changes = text, []
                print("No numbers to review.")
        else:
            # Headless: process() classifies and applies in one pass
            lines, proposals = processor.propose(text, ai_mode=args.ai_mode)
            # Write proposals report for preview
            write_proposals_report(proposals, input_path, dry_run=False)
            # Now apply the proposals
            output_text, changes = processor.apply_proposals(text, proposals)

    except Exception as e:
        print(f"Error processing text: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Write output
    try:
        output_path.write_text(output_text, encoding="utf-8")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nOutput: {output_path}")
    print(f"  Numbers formatted: {len(changes)}")

    # Print change summary
    if changes:
        print(f"\nChanges (first 10):")
        for c in changes[:10]:
            print(f"\nLine {c['line']:4d}")
            print(f"  Original:  {c['original']!r}")
            print(f"  Formatted: {c['formatted']!r}")
            print(f"  Type:      {c['type']}, Rule: {c['rule']}")
            print(f"  Sentence:  {c['full_sentence']}")
        if len(changes) > 10:
            print(f"\n  ... and {len(changes) - 10} more")
    else:
        print("\nNo numbers formatted (all matched default rule or were unchanged)")

    # Write detailed report to file
    try:
        report_path = LOGS_DIR / (input_path.stem + "_number_changes.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("NUMBER FORMATTING REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Input file:  {input_path}\n")
            f.write(f"Output file: {output_path}\n")
            f.write(f"Total changes: {len(changes)}\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write("DETAILED CHANGES\n")
            f.write("=" * 80 + "\n\n")

            for c in changes:
                f.write(f"Line {c['line']:4d}\n")
                f.write(f"  Original:  {c['original']!r}\n")
                f.write(f"  Formatted: {c['formatted']!r}\n")
                f.write(f"  Type:      {c['type']}\n")
                f.write(f"  Rule:      {c['rule']}\n")
                f.write(f"  Sentence:  {c['full_sentence']}\n")
                f.write("\n")

        print(f"\nReport: {report_path}")
    except Exception as e:
        print(f"Warning: Could not write report file: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
