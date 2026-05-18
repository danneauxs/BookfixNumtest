"""
Rules-only number processor adapter.

Extracts the rule-based number classification and formatting logic
from AINumberedLineProcessor, bypassing AI initialization.

Uses spaCy NER as primary classifier for robust entity recognition.
"""

import os
import re
import json
from typing import Tuple, List, Dict, Optional
from pathlib import Path
import spacy
from spacy.matcher import Matcher
from num2words import num2words
from ai_numbered_processor import AINumberedLineProcessor
from ai.service import BookfixAIService


class RulesOnlyNumberProcessor:
    """
    Processes text to format numbers for TTS using rules only (no AI, no UI).

    Classification order:
    1. spaCy NER: DATE/TIME/MONEY/ORDINAL/PERCENT → direct type mapping
    2. For CARDINAL: prefix keyword rules (room, page, code, temperature)
    3. Fallback: general_number (safe default)
    """

    def __init__(self):
        """Initialize the processor with NER and rules-only mode."""
        self.processor = AINumberedLineProcessor()
        self.processor.rules_only_mode = True  # Skips AI fallback in _get_number_type
        self.processor.use_pos_analysis = False  # Disable optional POS analysis
        self.processor.learning_storage = None  # Disable stale learned patterns

        # Initialize AI service for number classification
        try:
            # Look for ai_config.json in numtest root directory
            config_path = os.path.join(os.path.dirname(__file__), "ai_config.json")
            with open(config_path) as f:
                ai_config = json.load(f)
            self.ai_service = BookfixAIService(**ai_config)
        except (ImportError, ModuleNotFoundError, FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: AI service failed to initialize: {e}")
            self.ai_service = None

        # Load spaCy model for NER classification
        try:
            self.nlp = spacy.load("en_core_web_md")
        except OSError:
            print("Warning: en_core_web_md not found, falling back to en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        # Build spaCy Matcher for noun+digit identifier patterns
        self.matcher = Matcher(self.nlp.vocab)
        # FIX 1B: Added "box" (P.O. boxes) and "pattern" (military/code patterns)
        identifier_nouns = [
            # Locations
            "room", "suite", "apartment", "apt", "unit", "cabin", "cell", "box",
            # Transport
            "flight", "route", "train", "bus", "gate", "platform",
            # Spy/Military
            "agent", "operative", "officer", "contact", "case", "pattern",
            # Document/Media
            "chapter", "page", "verse", "section", "paragraph", "episode", "season", "part",
            # Codes/Classifications
            "code", "serial", "reference", "ref", "pin", "zip", "model", "type", "class", "grade", "level",
        ]
        # Pattern 1: NOUN + DIGIT (e.g., "Room 501")
        self.matcher.add("IDENTIFIER", [
            [
                {"LOWER": {"IN": identifier_nouns}},
                {"IS_DIGIT": True},
            ]
        ])

        # Keyword sets for prefix-based CARDINAL classification
        self.room_words = {"room", "suite", "apartment", "apt", "unit", "cabin", "cell"}
        # FIX 1A: Added "box" (P.O. boxes) and "pattern" (military/code patterns)
        self.page_words = {"page", "pg", "p.", "paragraph", "chapter", "verse", "stanza", "box", "pattern"}
        self.code_words = {"code", "serial", "number", "ref", "id", "pin", "zip"}
        self.temp_words = {"temperature", "temp", "fever", "degrees"}

    def process(self, text: str) -> Tuple[str, List[Dict]]:
        """
        Process text to format numbers using NER + rules (backward-compatible headless).

        This method classifies and applies changes in one pass for headless usage.
        For interactive review, use propose() + apply_proposals() instead.

        Args:
            text: Input text to process

        Returns:
            Tuple of (processed_text, change_records)
        """
        lines, proposals = self.propose(text)
        return self.apply_proposals(text, proposals)

    def propose(self, text: str, ai_mode: str = "rules_then_ai") -> Tuple[List[str], List[Dict]]:
        """
        Propose number formatting changes without applying them.

        Returns the original lines and a list of proposals with character positions.
        Each proposal can be reviewed/edited before calling apply_proposals().

        Args:
            text: Input text to analyze

        Returns:
            Tuple of (original_lines, proposals)
            - original_lines: text.splitlines()
            - proposals: List of dicts with line_no, start, end, original, formatted, type, rule, full_sentence, user_text, accepted
        """
        # Step 1: Analyze document-level context
        text_context = self.processor._analyze_text_context(text)

        # Step 2: Find all numbered lines using regex
        numbered_lines = self.processor._find_all_numbers_for_ai(text)

        # Step 3: Classify each number and build proposals
        proposals: List[Dict] = []
        lines = text.splitlines(keepends=False)

        for line_no, line_content, spans in numbered_lines:
            # Process each number in the line
            for start, end in spans:
                number = line_content[start:end]
                ctx_before = line_content[max(0, start - 50) : start]
                ctx_after = line_content[end : end + 50]

                # Classify: Compound → Matcher → NER → prefix rules → full rules
                compound_type = self._detect_compound(number)

                if compound_type:
                    # Compound hyphenated number (e.g., 487-29-3875, 3,000-4,000K)
                    number_type, rule_source = compound_type
                else:
                    matcher_type = self._matcher_classify(line_content, start, end)

                    if matcher_type:
                        # spaCy Matcher found a noun+digit identifier pattern
                        number_type = matcher_type
                        rule_source = "spacy_matcher"
                    else:
                        # Try NER classification
                        ner_type = self._ner_classify(line_content, start, end)

                        if ner_type:
                            number_type = ner_type
                            rule_source = "spacy_ner"
                            # FIX 1 & 2: NER currency guard — check all currency symbols, not just $
                            if number_type == "currency" and not re.match(r"[\$£€¥₹¢]", number):
                                currency_symbols = "$£€¥₹¢"
                                found_sym = next((s for s in currency_symbols if s in ctx_before[-5:]), None)
                                if found_sym:
                                    number = found_sym + number
                                else:
                                    # No currency symbol found — NER was wrong, use as general_number
                                    number_type = "general_number"
                                    rule_source = "ner_currency_fallback"
                            # FIX 5 & 6: Year plausibility guard — NER DATE must be 4-digit year in valid range
                            # FIX 6: Check for hyphen-prefix alphanumeric identifier (QF-74843)
                            elif number_type == "year":
                                # FIX 1: Check if it's actually a clock time (9:38, 14.30) first
                                if re.match(r'^\d{1,2}[:.]\d{2}$', number):
                                    number_type = "clock_time"
                                    rule_source = "ner_date_to_time"
                                else:
                                    try:
                                        year_val = int(number.replace(",", ""))
                                        if not (1000 <= year_val <= 2150) or len(number.replace(",", "")) != 4:
                                            # FIX 5: Check for ZIP code (5-digit after 2-letter state abbr: FL 33731)
                                            if re.search(r'\b[A-Z]{2}\s*$', ctx_before) and re.match(r'^\d{5}$', number):
                                                number_type = "identifier"
                                                rule_source = "rule_zip_code"
                                            # FIX 6: Check if preceded by hyphenated code prefix
                                            elif ctx_before.rstrip().endswith("-"):
                                                number_type = "identifier"
                                                rule_source = "ner_year_hyphen_id"
                                            else:
                                                number_type = "general_number"
                                                rule_source = "ner_year_fallback"
                                    except ValueError:
                                        number_type = "general_number"
                                        rule_source = "ner_year_fallback"
                            # FIX 4: After NER downgrade, check for street address pattern (387 Obsidian Road)
                            if number_type == "general_number" and rule_source in ("ner_currency_fallback", "ner_year_fallback"):
                                # FIX 1: Don't reclassify clock-like numbers (9:38, 14.30) as street addresses
                                if not re.match(r'^\d{1,2}[:.]\d{2}$', number):
                                    street_suffixes = {
                                        "street", "road", "avenue", "ave", "lane", "drive", "boulevard",
                                        "blvd", "court", "place", "way", "close", "terrace", "row", "crescent"
                                    }
                                    if any(re.search(r'\b' + w + r'\b', ctx_after, re.I) for w in street_suffixes):
                                        number_type = "identifier"
                                        rule_source = "rule_street_address_post_ner"
                        else:
                            # Try prefix rules for CARDINAL
                            cardinal_type = self._classify_cardinal(number, ctx_before, ctx_after)
                            if cardinal_type:
                                number_type, rule_source = cardinal_type
                            else:
                                # Final fallback to full rules
                                number_type, rule_source = self.processor._get_number_type(
                                    number, ctx_before, ctx_after, text_context
                                )

                # Format
                if number_type in ("range_currency", "range_measurement"):
                    formatted = self._format_compound(number, number_type)
                elif number_type == "clock_time":
                    # FIX 4: Check for "hours" suffix to detect military time format
                    is_military = bool(re.search(r'\bhours?\b', ctx_after, re.I))
                    formatted = self._try_format_clock_time(number, military=is_military)
                    if formatted is None:
                        formatted = self.processor._format_number_by_type(number, "general_number")
                        number_type = "general_number"
                elif number_type == "identifier" and compound_type:
                    # Compound identifier
                    formatted = self._format_compound(number, number_type)
                else:
                    formatted = self.processor._format_number_by_type(number, number_type)

                # FIX 2: Zero-after-dash TTS clarity (WF-075, XAE-0900)
                # If identifier starts with "0" and preceded by dash, prepend space for TTS clarity
                if number_type == "identifier" and formatted and formatted[0] == "0" and ctx_before.rstrip().endswith("-") and not compound_type:
                    formatted = " " + formatted

                # Record proposal if formatting differs
                if formatted != number:
                    full_sentence = self._extract_sentence(line_content, start, end)

                    proposals.append(
                        {
                            "line": line_no + 1,  # 1-based for display
                            "line_no": line_no,  # 0-based for indexing
                            "start": start,  # char offset in original line
                            "end": end,  # char offset in original line
                            "original": number,
                            "formatted": formatted,
                            "type": number_type,
                            "rule": rule_source,
                            "full_sentence": full_sentence,
                            "user_text": formatted,  # user can edit this
                            "accepted": True,  # user can change this
                        }
                    )

        # FIX 7: Merge dashed compound identifiers (487-29-3875 → "4 8 7 dash 2 9 dash 3 8 7 5")
        proposals = self._merge_hyphenated_identifiers(proposals, lines)

        # AI classification: rules_then_ai or ai_only mode
        if self.ai_service and ai_mode in ("rules_then_ai", "ai_only"):
            try:
                # Filter proposals: all for ai_only, only general_number for rules_then_ai
                candidates = proposals if ai_mode == "ai_only" else [p for p in proposals if p["type"] == "general_number"]

                if candidates:
                    batch_items = [
                        {"id": proposals.index(p), "number": p["original"], "context": p["full_sentence"]}
                        for p in candidates
                    ]
                    ai_results = self.ai_service.classify_numbers_batch(batch_items)

                    # Type mapping from AI to internal types
                    type_map = {
                        "year": "year", "quantity": "general_number", "measurement": "measurement",
                        "identifier": "identifier", "currency": "currency", "ordinal": "ordinal",
                        "military_time": "clock_time", "elapsed_time": "clock_time", "general_number": "general_number",
                    }

                    for idx, response in ai_results.items():
                        if response.success:
                            new_type = type_map.get(response.content, "general_number")
                            proposals[idx]["type"] = new_type
                            proposals[idx]["formatted"] = self.reformat(proposals[idx]["original"], new_type)
                            proposals[idx]["user_text"] = proposals[idx]["formatted"]
                            proposals[idx]["rule"] += "_ai"
            except Exception as e:
                print(f"Warning: AI classification failed, using rules only: {e}")

        return lines, proposals

    def apply_proposals(
        self, text: str, proposals: List[Dict]
    ) -> Tuple[str, List[Dict]]:
        """
        Apply reviewed proposals to the original text.

        Args:
            text: Original text (unmodified)
            proposals: List from propose(), possibly edited by user

        Returns:
            Tuple of (output_text, applied_changes)
            - output_text: Text with accepted proposals applied
            - applied_changes: List of proposals that were actually applied
        """
        lines = text.splitlines(keepends=False)

        # Group proposals by line for in-order processing
        from collections import defaultdict

        by_line = defaultdict(list)
        for p in proposals:
            if p.get("accepted", True) and p["user_text"] != p["original"]:
                by_line[p["line_no"]].append(p)

        # Apply proposals line by line, tracking offset
        applied = []
        for line_no in sorted(by_line.keys()):
            line_proposals = sorted(by_line[line_no], key=lambda p: p["start"])
            new_line = lines[line_no]
            offset = 0

            for p in line_proposals:
                adj_start = p["start"] + offset
                adj_end = p["end"] + offset
                new_line = new_line[:adj_start] + p["user_text"] + new_line[adj_end:]
                offset += len(p["user_text"]) - len(p["original"])
                applied.append(p)

            lines[line_no] = new_line

        return "\n".join(lines), applied

    def _merge_hyphenated_identifiers(self, proposals: List[Dict], lines: List[str]) -> List[Dict]:
        """
        FIX 7: Merge adjacent identifier/range proposals separated by hyphens.

        1. If two consecutive identifiers are separated by only a hyphen, merge them
           as a compound identifier (487-29-3875).
        2. If two adjacent proposals are separated by only a hyphen and the second is
           a measurement, merge them into a range (3,000-4,000 LB).

        Args:
            proposals: List of proposals from propose()
            lines: Original text lines

        Returns:
            Modified proposals list with merged dashed identifiers and ranges
        """
        if not proposals:
            return proposals

        # Group proposals by line_no
        from collections import defaultdict
        by_line = defaultdict(list)
        for p in proposals:
            by_line[p["line_no"]].append(p)

        merged = []
        for line_no in sorted(by_line.keys()):
            line_props = sorted(by_line[line_no], key=lambda p: p["start"])
            line_text = lines[line_no]

            i = 0
            while i < len(line_props):
                p1 = line_props[i]

                # Check if next proposal exists and separated by dash/hyphen
                if i + 1 < len(line_props):
                    p2 = line_props[i + 1]
                    # Check if separated by only a hyphen: p1.end == p2.start - 1 and char is '-'
                    if p2["start"] == p1["end"] + 1 and p1["end"] < len(line_text) and line_text[p1["end"]] == "-":
                        # Case 1: Merge identifiers (487-29-3875)
                        if ((p1["type"] == "identifier" and p2["type"] == "identifier") or
                            (p2["type"] == "identifier")):

                            # Merge p1 and p2
                            merged_original = p1["original"] + "-" + p2["original"]

                            # Format as digit-by-digit with " dash " between
                            digits1 = re.sub(r"[^\d]", "", p1["original"])
                            digits2 = re.sub(r"[^\d]", "", p2["original"])
                            merged_formatted = " ".join(list(digits1)) + " dash " + " ".join(list(digits2))

                            merged.append({
                                "line": p1["line"],
                                "line_no": p1["line_no"],
                                "start": p1["start"],
                                "end": p2["end"],
                                "original": merged_original,
                                "formatted": merged_formatted,
                                "type": "identifier",
                                "rule": "rule_merged_hyphen_id",
                                "full_sentence": p1["full_sentence"],
                                "user_text": merged_formatted,
                                "accepted": True,
                            })
                            i += 2  # Skip both proposals
                            continue

                        # Case 2: Merge number + measurement as range (3,000-4,000 LB)
                        elif p2["type"] == "measurement":
                            # Format as range: "three thousand to four thousand"
                            try:
                                num1_str = re.sub(r"[^\d.]", "", p1["original"])
                                num2_str = re.sub(r"[^\d.]", "", p2["original"])

                                if num1_str and num2_str:
                                    # Format each number
                                    if "." in num1_str:
                                        num1_formatted = num2words(float(num1_str))
                                    else:
                                        num1_formatted = num2words(int(num1_str))

                                    if "." in num2_str:
                                        num2_formatted = num2words(float(num2_str))
                                    else:
                                        num2_formatted = num2words(int(num2_str))

                                    # Extract unit from p2
                                    unit = re.sub(r'\d|\.|\s', '', p2["original"]).strip()

                                    merged_formatted = f"{num1_formatted} to {num2_formatted}"
                                    if unit:
                                        merged_formatted += f" {unit}"

                                    merged_original = p1["original"] + "-" + p2["original"]

                                    merged.append({
                                        "line": p1["line"],
                                        "line_no": p1["line_no"],
                                        "start": p1["start"],
                                        "end": p2["end"],
                                        "original": merged_original,
                                        "formatted": merged_formatted,
                                        "type": "range_measurement",
                                        "rule": "rule_range_merge",
                                        "full_sentence": p1["full_sentence"],
                                        "user_text": merged_formatted,
                                        "accepted": True,
                                    })
                                    i += 2  # Skip both proposals
                                    continue
                            except (ValueError, OverflowError):
                                pass  # Fall through to no-merge case

                # No merge: add p1 as-is
                merged.append(p1)
                i += 1

        return merged

    def reformat(
        self, number: str, number_type: str, currency_symbol: str = "$"
    ) -> str:
        """
        Re-format a number with a specific type (used by review window).

        Args:
            number: Original number string (e.g., "59200", "$150", "3.30", "3,000-4,000K")
            number_type: Classification type (general_number, year, identifier, range_measurement, etc.)
            currency_symbol: Default currency symbol ($, £, €, ¥)

        Returns:
            Formatted string (e.g., "5 9 2 0 0" for identifier)
        """
        if number_type == "identifier":
            # Digit by digit
            digits = re.sub(r"[^\d]", "", number)
            return " ".join(list(digits)) if digits else number

        if number_type in ("range_currency", "range_measurement"):
            return self._format_compound(number, number_type)

        if number_type == "clock_time":
            result = self._try_format_clock_time(number)
            return result if result else number

        if number_type == "currency":
            # Ensure currency symbol is present
            if not re.match(r"[\$£€¥]", number):
                number = currency_symbol + number

        return self.processor._format_number_by_type(number, number_type)

    def _matcher_classify(self, line: str, start: int, end: int) -> Optional[str]:
        """
        Use spaCy Matcher to detect noun+digit identifier patterns (Room 501, Flight 396, etc).

        Returns 'identifier' if a noun+digit pattern covers the number, else None.
        """
        try:
            doc = self.nlp(line)
            matches = self.matcher(doc)
            for match_id, tok_start, tok_end in matches:
                # Check if the digit token in the match covers our number span
                digit_token = doc[tok_end - 1]
                if digit_token.idx == start and digit_token.idx + len(digit_token.text) == end:
                    return "identifier"
        except Exception:
            pass
        return None

    def _ner_classify(self, line: str, start: int, end: int) -> Optional[str]:
        """
        Use spaCy NER to classify the number at [start:end] in the line.

        Returns the classification type (year, clock_time, currency, ordinal, measurement)
        or None if NER returns CARDINAL or doesn't cover the span.
        """
        try:
            doc = self.nlp(line)
            for ent in doc.ents:
                # Check if this entity overlaps with our number span
                if ent.start_char <= start and ent.end_char >= end:
                    label_map = {
                        "DATE": "year",
                        "TIME": "clock_time",
                        "MONEY": "currency",
                        "ORDINAL": "ordinal",
                        "PERCENT": "measurement",
                    }
                    return label_map.get(ent.label_)  # None for CARDINAL, ORG, etc.
        except Exception:
            pass  # Fall through to rules if NER fails
        return None

    def _classify_cardinal(
        self, number: str, ctx_before: str, ctx_after: str
    ) -> Optional[Tuple[str, str]]:
        """
        Classify CARDINAL numbers using prefix/suffix keyword rules.

        Returns (type, rule_source) or None to fall back to full rules.
        """
        before_words = ctx_before.strip().rstrip(".,;:-'\"").split()
        last_word = before_words[-1].lower() if before_words else ""

        after_words = ctx_after.strip().split()
        first_word = after_words[0].lower() if after_words else ""

        # Clock time pattern: 3.30, 14.45, 6:05, etc. (before rules to catch these early)
        if re.match(r"^\d{1,2}[.:]\d{2}$", number):
            # Check context suggests time (before, after, at, etc.)
            time_keywords = {"before", "after", "at", "around", "by", "until", "till", "from", "the", "was", "is"}
            if last_word in time_keywords or re.search(r"(arrive|depart|take off|meeting|appointment|clock|time)\b", ctx_before + ctx_after, re.I):
                return ("clock_time", "rule_clock_time")

        # Dash-preceded number (WF-075, QF-123) — always identifier
        if ctx_before.rstrip().endswith("-"):
            return ("identifier", "rule_dash_prefix")

        # FIX 1C: US highway/road/route number (US 301, SR 450, Hwy 95, Interstate 75)
        if re.search(r'\b(US|SR|Hwy|Route|Interstate|I-)\s*$', ctx_before, re.I):
            return ("identifier", "rule_highway")

        # Room/suite/apartment pattern
        if last_word in self.room_words:
            return ("identifier", "rule_room")

        # Page/chapter/verse pattern
        if last_word in self.page_words:
            return ("identifier", "rule_page")

        # Code/serial/number reference pattern
        if re.search(r"\b(code|serial|number\s+(is|was|:))\b", ctx_before, re.I):
            return ("identifier", "rule_code")

        # Temperature pattern
        if last_word in self.temp_words:
            return ("general_number", "rule_temperature")

        # Dollar sign before number (catches $150 if NER missed it)
        if "$" in ctx_before[-3:]:
            return ("currency", "rule_dollar_prefix")

        # FIX 5: US ZIP code (5-digit number after 2-letter state abbreviation: FL 33731)
        if re.search(r'\b[A-Z]{2}\s*$', ctx_before) and re.match(r'^\d{5}$', number):
            return ("identifier", "rule_zip_code")

        # FIX 2: Street address pattern — number followed by street suffix (159 Vigo Street)
        street_suffixes = {
            "street", "road", "avenue", "ave", "lane", "drive", "boulevard",
            "blvd", "court", "place", "way", "close", "terrace", "row", "crescent"
        }
        if any(re.search(r'\b' + w + r'\b', ctx_after, re.I) for w in street_suffixes):
            return ("identifier", "rule_street_address")

        # FIX 3: Expand exclusion list for rule_noun_follows (add prepositions/function words)
        # Prepositions after a number usually mean code/title + prepositional phrase, not "quantity + noun"
        _noun_follows_stop = {
            "and", "or", "the", "a", "an",
            "to", "of", "in", "with", "for", "at", "from", "into", "on", "upon",
            "by", "as", "up", "if", "so", "is", "was", "has", "have", "had", "be",
        }
        # Noun follows the number (marks as general quantity)
        if first_word and re.match(r"^[a-z]+$", first_word) and first_word not in _noun_follows_stop:
            return ("general_number", "rule_noun_follows")

        return None

    def _detect_compound(self, number: str) -> Optional[Tuple[str, str]]:
        """
        Detect if a number is a compound hyphenated number and classify it.

        Returns (type, rule_source) or None if not a compound.

        Examples:
        - "487-29-3875" (3+ segments) → identifier
        - "$300-400" (2 segments, currency) → range_currency
        - "3,000-4,000K" (2 segments, unit letter) → range_measurement
        - "487-756" (2 segments, no context) → identifier
        """
        # Check if it looks like a compound (has at least one hyphen between number segments)
        if not re.search(r'\d+-\d+', number):
            return None

        # Extract segments (currency prefix, number groups, optional unit suffix)
        segments = re.split(r'-', number)
        segment_count = len(segments)

        # Must have at least 2 segments
        if segment_count < 2:
            return None

        # Check for currency symbol (at the start)
        has_currency = bool(re.match(r'^[\$£€¥]', number))

        # Check for unit letter (at the end, single uppercase letter)
        has_unit = bool(re.match(r'.*[A-Z]$', number))
        unit_letter = number[-1] if has_unit and number[-1].isalpha() else None

        # Classify based on structure
        if segment_count >= 3:
            # 3+ segments always identifier (487-29-3875)
            return ("identifier", "rule_compound_identifier")
        elif segment_count == 2:
            # 2 segments: check year range, currency, or unit
            if has_currency:
                return ("range_currency", "rule_range_currency")
            elif has_unit:
                return ("range_measurement", "rule_range_measurement")
            else:
                # Check for year range: 4-digit year + 2-digit abbreviation (e.g. "1960-62")
                first, second = segments[0], segments[1]
                if re.match(r'^\d{4}$', first) and re.match(r'^\d{2}$', second):
                    first_year = int(first)
                    if 1900 <= first_year <= 2099:
                        return ("year_range", "rule_year_range")
                # Default to identifier, user can override to range
                return ("identifier", "rule_compound_identifier")

        return None

    def _format_compound(self, number: str, number_type: str) -> str:
        """
        Format a compound hyphenated number based on its type.

        Args:
            number: Compound number string (e.g., "487-29-3875", "3,000-4,000K", "$300-400")
            number_type: Classification (identifier, range_currency, range_measurement)

        Returns:
            Formatted string
        """
        if number_type == "identifier":
            # Digit-by-digit with " dash " between segments
            segments = re.split(r'-', number)
            formatted_segments = []
            for seg in segments:
                # Remove commas and currency symbols, extract digits only
                digits = re.sub(r'[^\d]', '', seg)
                if digits:
                    formatted_segments.append(" ".join(list(digits)))
            return " dash ".join(formatted_segments)

        elif number_type == "range_currency":
            # Extract currency symbol, format numbers, append currency name
            match = re.match(r'^([\$£€¥])(.*)', number)
            if not match:
                return number

            currency_symbol = match.group(1)
            rest = match.group(2)
            segments = re.split(r'-', rest)

            # Map symbols to currency names
            currency_names = {
                "$": "dollars",
                "£": "pounds",
                "€": "euros",
                "¥": "yen",
            }
            currency_name = currency_names.get(currency_symbol, "")

            # Format each segment as a number (remove commas)
            formatted_parts = []
            for seg in segments:
                num_str = seg.replace(",", "")
                try:
                    num_val = int(num_str)
                    formatted_parts.append(num2words(num_val))
                except (ValueError, OverflowError):
                    formatted_parts.append(seg)

            result = " to ".join(formatted_parts)
            if currency_name:
                result += f" {currency_name}"
            return result

        elif number_type == "range_measurement":
            # Format numbers, join with " to ", append unit letter
            unit = number[-1] if number and number[-1].isalpha() else ""
            rest = number[:-1] if unit else number
            segments = re.split(r'-', rest)

            # Format each segment as a number
            formatted_parts = []
            for seg in segments:
                num_str = seg.replace(",", "").replace(unit, "")
                try:
                    # Handle decimals
                    if "." in num_str:
                        num_val = float(num_str)
                        formatted_parts.append(num2words(num_val))
                    else:
                        num_val = int(num_str)
                        formatted_parts.append(num2words(num_val))
                except (ValueError, OverflowError):
                    formatted_parts.append(num_str)

            result = " to ".join(formatted_parts)
            if unit:
                result += f" {unit}"
            return result

        return number

    def _try_format_clock_time(self, number: str, military: bool = False) -> Optional[str]:
        """
        Try to format a number as a clock time.

        Args:
            number: Time string (HH.MM or HH:MM format)
            military: If True, format as military time (0800 hours); else conversational (eight o'clock)

        Returns formatted time or None if the number isn't a valid time.
        Valid times must have exactly 2 decimal digits (HH.MM format),
        hours 0-23, and minutes 00-59. Rejects 3.142 (pi), 4.5, etc.
        """
        parts = re.split(r"[.:]", number)
        if len(parts) != 2:
            return None

        # Must be exactly 2 decimal digits (not 3.142, not 3.1)
        if len(parts[1]) != 2:
            return None

        try:
            h, m = int(parts[0]), int(parts[1])
        except ValueError:
            return None

        # Validate time range
        if h > 23 or m > 59:
            return None  # Not a valid time → treat as decimal

        # Valid time: format as spoken
        if military:
            # Military time format: 0800 → "zero eight hundred"
            h_str = f"zero {num2words(h)}" if h < 10 else num2words(h)
            if m == 0:
                return f"{h_str} hundred"
            elif m < 10:
                return f"{h_str} oh {num2words(m)}"
            else:
                return f"{h_str} {num2words(m)}"

        # Conversational time format
        hour_word = num2words(h)
        if m == 0:
            return f"{hour_word} o'clock"
        elif m < 10:
            return f"{hour_word} oh {num2words(m)}"
        else:
            return f"{hour_word} {num2words(m)}"

    def _extract_sentence(self, line: str, number_start: int, number_end: int) -> str:
        """
        Extract the complete sentence containing a number.

        A sentence ends with . ! or ?
        """
        # Find sentence start (after previous . ! or ?)
        sent_start = 0
        for i in range(number_start - 1, -1, -1):
            if line[i] in '.!?':
                sent_start = i + 1
                break

        # Find sentence end (next . ! or ?)
        sent_end = len(line)
        for i in range(number_end, len(line)):
            if line[i] in '.!?':
                sent_end = i + 1
                break

        # Extract and clean up
        sentence = line[sent_start:sent_end].strip()
        return sentence
