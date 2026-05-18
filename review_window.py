"""
Interactive PyQt5 review window for number formatting proposals.

Allows user to confirm, correct, or reclassify each proposed number format
using quick keyboard shortcuts and an editable output field.
"""

from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QProgressBar,
    QGroupBox,
    QFrame,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QTextCursor, QTextCharFormat, QColor


class NumberReviewWindow(QDialog):
    """
    Interactive review window for number formatting proposals.

    Shows each proposed change with context, allows user to:
    - Accept/reject changes
    - Change classification type using quick keys (1-7)
    - Edit output text directly
    - Navigate between changes
    """

    def __init__(self, original_text: str, proposals: List[Dict], processor, parent=None):
        """
        Args:
            original_text: Original input text
            proposals: List of proposal dicts from rules_processor.propose()
            processor: RulesOnlyNumberProcessor instance for re-formatting
            parent: Parent widget
        """
        super().__init__(parent)
        self.original_text = original_text
        self.original_lines = original_text.splitlines(keepends=False)
        self.proposals = proposals
        self.processor = processor

        self.current_index = 0
        self.setWindowTitle("Number Review")
        self.resize(1000, 600)

        self.setup_ui()
        self.show_proposal(0)

    def setup_ui(self):
        """Build the UI layout."""
        main_layout = QVBoxLayout(self)

        # Top: title and progress bar
        header = QHBoxLayout()
        self.title_label = QLabel()
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(20)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.progress, 0)
        main_layout.addLayout(header)

        # Main content: splitter with context (left) and controls (right)
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: context display
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("SENTENCE:"))
        self.context_edit = QTextEdit()
        self.context_edit.setReadOnly(True)
        self.context_edit.setMaximumWidth(400)
        left_layout.addWidget(self.context_edit)
        splitter.addWidget(left_panel)

        # Right panel: controls
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        # Info section
        info_group = QGroupBox("Current Change")
        info_layout = QVBoxLayout(info_group)
        self.original_label = QLabel()
        self.type_label = QLabel()
        info_layout.addWidget(self.original_label)
        info_layout.addWidget(self.type_label)
        right_layout.addWidget(info_group)

        # Output section
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        output_layout.addWidget(QLabel("Formatted (edit to customize):"))

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        output_row.addWidget(self.output_edit, 1)

        self.all_btn = QPushButton("All")
        self.all_btn.setMaximumWidth(50)
        self.all_btn.clicked.connect(self.apply_to_all)
        output_row.addWidget(self.all_btn)

        output_layout.addLayout(output_row)
        right_layout.addWidget(output_group)

        # Type selector buttons
        type_group = QGroupBox("Type (quick keys)")
        type_layout = QVBoxLayout(type_group)

        row1 = QHBoxLayout()
        self.type_buttons = {}
        for i, (key, label) in enumerate(
            [
                (1, "General"),
                (2, "Year"),
                (3, "Code/ID"),
                (4, "Currency"),
            ]
        ):
            btn = QPushButton(f"[{key}] {label}")
            btn.setMaximumWidth(120)
            btn.clicked.connect(lambda checked=False, k=key: self.select_type(k))
            row1.addWidget(btn)
            self.type_buttons[key] = btn

        type_layout.addLayout(row1)

        row2 = QHBoxLayout()
        for i, (key, label) in enumerate(
            [
                (5, "Time"),
                (6, "Measure"),
                (7, "Ordinal"),
                (8, "Range"),
            ]
        ):
            btn = QPushButton(f"[{key}] {label}")
            btn.setMaximumWidth(120)
            btn.clicked.connect(lambda checked=False, k=key: self.select_type(k))
            row2.addWidget(btn)
            self.type_buttons[key] = btn

        # Skip button (key 0)
        skip_type_btn = QPushButton("[0] Skip")
        skip_type_btn.setMaximumWidth(120)
        skip_type_btn.clicked.connect(lambda checked=False, k=0: self.select_type(k))
        row2.addWidget(skip_type_btn)
        self.type_buttons[0] = skip_type_btn

        type_layout.addLayout(row2)

        # Flag button (key 9)
        row3 = QHBoxLayout()
        flag_btn = QPushButton("[9] Flag (!!FLASH!!)")
        flag_btn.setMaximumWidth(150)
        flag_btn.clicked.connect(self.flag_number)
        row3.addWidget(flag_btn)
        row3.addStretch()
        type_layout.addLayout(row3)

        right_layout.addWidget(type_group)

        # Currency symbol selector (hidden by default)
        self.currency_group = QGroupBox("Currency")
        currency_layout = QHBoxLayout(self.currency_group)
        self.currency_buttons = {}
        for i, symbol in enumerate(["$", "£", "€", "¥"]):
            btn = QPushButton(f"{i+1}) {symbol}")
            btn.setMaximumWidth(70)
            btn.clicked.connect(lambda checked=False, s=symbol: self.select_currency(s))
            currency_layout.addWidget(btn)
            self.currency_buttons[i + 1] = (btn, symbol)
        self.currency_group.hide()
        right_layout.addWidget(self.currency_group)

        right_layout.addStretch()

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        # Bottom buttons
        button_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Prev")
        self.prev_btn.clicked.connect(self.previous_proposal)
        button_layout.addWidget(self.prev_btn)

        self.skip_btn = QPushButton("→ Skip")
        self.skip_btn.clicked.connect(self.next_proposal)
        button_layout.addWidget(self.skip_btn)

        self.accept_btn = QPushButton("✓ Accept (Enter)")
        self.accept_btn.clicked.connect(self.accept_proposal)
        self.accept_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        button_layout.addWidget(self.accept_btn)

        button_layout.addStretch()

        self.apply_btn = QPushButton("Apply & Save")
        self.apply_btn.clicked.connect(self.apply_and_save)
        self.apply_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.apply_btn.setEnabled(False)
        button_layout.addWidget(self.apply_btn)

        self.skip_all_btn = QPushButton("Skip Remaining")
        self.skip_all_btn.clicked.connect(self.skip_remaining)
        button_layout.addWidget(self.skip_all_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)

    def _get_expanded_context(self, proposal: Dict) -> str:
        """
        Extract ~150 chars before and after the number, skipping blank lines.

        Returns context string with the number marked with « » boundaries.
        """
        line_no = proposal["line_no"]
        start = proposal["start"]
        end = proposal["end"]
        num = proposal["original"]

        # Phase 1: Collect backward (~150 chars, skipping blank lines)
        before = ""
        chars_collected = 0
        current_line = line_no
        current_pos = start

        while current_line >= 0 and chars_collected < 150:
            line = self.original_lines[current_line]

            if current_line == line_no:
                # Same line: take [0:start]
                segment = line[:current_pos]
            else:
                # Previous line: take entire line
                segment = line

            # Only count non-blank content
            if segment.strip():
                before = segment + before
                chars_collected += len(segment)

            current_line -= 1
            current_pos = len(line) if current_line >= 0 else 0

        # Phase 2: Collect forward (~150 chars, skipping blank lines)
        after = ""
        chars_collected = 0
        current_line = line_no
        current_pos = end

        while current_line < len(self.original_lines) and chars_collected < 150:
            line = self.original_lines[current_line]

            if current_line == line_no:
                # Same line: take [end:]
                segment = line[current_pos:]
            else:
                # Next line: take entire line
                segment = line

            # Only count non-blank content
            if segment.strip():
                after = after + segment
                chars_collected += len(segment)

            current_line += 1
            current_pos = 0

        # Assemble with visual markers
        return f"{before} » {num} « {after}"

    def show_proposal(self, index: int):
        """Display the proposal at the given index."""
        if index < 0 or index >= len(self.proposals):
            return

        self.current_index = index
        p = self.proposals[index]

        # Update title and progress
        self.title_label.setText(f"Change {index + 1} of {len(self.proposals)}")
        self.progress.setValue(int((index + 1) / len(self.proposals) * 100))

        # Show context with number highlighted (expanded context, not just sentence)
        sentence = self._get_expanded_context(p)
        original_num = p["original"]
        self.context_edit.setText(sentence)

        # Highlight the number in yellow
        cursor = self.context_edit.textCursor()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#FFFF00"))

        idx = sentence.find(original_num)
        if idx != -1:
            cursor.setPosition(idx)
            cursor.setPosition(idx + len(original_num), QTextCursor.KeepAnchor)
            self.context_edit.setTextCursor(cursor)
            cursor.mergeCharFormat(fmt)

        # Show original and type (type name in bold red)
        self.original_label.setText(f"Original: {p['original']}")
        self.type_label.setTextFormat(Qt.RichText)
        type_html = f'Type: <b><span style="font-size:14pt; color:red;">{p["type"]}</span></b> [{p["rule"]}]'
        self.type_label.setText(type_html)

        # Show current output
        self.output_edit.setText(p["user_text"])
        self.output_edit.selectAll()

        # Update button states
        self.apply_btn.setEnabled(False)
        self.currency_group.hide()

    def select_type(self, type_key: int):
        """Re-format the current number with the selected type."""
        if type_key == 0:  # Skip: restore original
            self.proposals[self.current_index]["user_text"] = self.proposals[
                self.current_index
            ]["original"]
            self.proposals[self.current_index]["accepted"] = False
            self.output_edit.setText(self.proposals[self.current_index]["original"])
            return

        type_map = {
            1: "general_number",
            2: "year",
            3: "identifier",
            4: "currency",
            5: "clock_time",
            6: "measurement",
            7: "ordinal",
            8: "range_measurement",
        }

        if type_key not in type_map:
            return

        p = self.proposals[self.current_index]
        new_type = type_map[type_key]

        if type_key == 4:  # Currency: show symbol selector
            self.currency_group.show()
            return

        # Re-format with the new type
        formatted = self.processor.reformat(p["original"], new_type)
        self.proposals[self.current_index]["user_text"] = formatted
        self.proposals[self.current_index]["type"] = new_type
        self.output_edit.setText(formatted)

    def select_currency(self, symbol: str):
        """Select a currency symbol and re-format."""
        p = self.proposals[self.current_index]
        formatted = self.processor.reformat(p["original"], "currency", currency_symbol=symbol)
        self.proposals[self.current_index]["user_text"] = formatted
        self.proposals[self.current_index]["type"] = "currency"
        self.output_edit.setText(formatted)
        self.currency_group.hide()

    def flag_number(self):
        """Flag a problematic number with !!FLASH!! prefix for manual review."""
        p = self.proposals[self.current_index]
        original = p["original"]
        flagged_text = f"!!FLASH!! {original}"
        self.proposals[self.current_index]["user_text"] = flagged_text
        self.proposals[self.current_index]["accepted"] = True
        self.output_edit.setText(flagged_text)

    def apply_to_all(self):
        """Apply current output_edit text to all proposals with matching original number."""
        current = self.proposals[self.current_index]
        original = current["original"]
        new_text = self.output_edit.text()

        # Find all proposals with same original number and apply the change
        count = 0
        for p in self.proposals:
            if p["original"] == original:
                p["user_text"] = new_text
                count += 1

        if count > 1:
            print(f"Applied '{new_text}' to {count} instances of '{original}'")

    def accept_proposal(self):
        """Accept the current proposal and advance."""
        p = self.proposals[self.current_index]
        p["user_text"] = self.output_edit.text()
        p["accepted"] = True

        # Find next unreviewed, or enable apply button if all done
        self.current_index += 1
        if self.current_index < len(self.proposals):
            self.show_proposal(self.current_index)
        else:
            self.current_index = len(self.proposals) - 1
            self.apply_btn.setEnabled(True)

    def next_proposal(self):
        """Navigate to next without accepting."""
        self.current_index += 1
        if self.current_index < len(self.proposals):
            self.show_proposal(self.current_index)
        else:
            self.current_index = len(self.proposals) - 1
            self.apply_btn.setEnabled(True)

    def previous_proposal(self):
        """Navigate to previous."""
        self.current_index -= 1
        if self.current_index >= 0:
            self.show_proposal(self.current_index)
        else:
            self.current_index = 0

    def skip_remaining(self):
        """Mark all remaining as accepted and enable apply."""
        for i in range(self.current_index, len(self.proposals)):
            p = self.proposals[i]
            if "user_text" not in p or p["user_text"] == p["formatted"]:
                p["user_text"] = p["formatted"]
            p["accepted"] = True

        self.apply_btn.setEnabled(True)

    def apply_and_save(self):
        """Apply all proposals and close."""
        self.accept()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()

        # 1-4: currency selection (when currency group is visible)
        if self.currency_group.isVisible() and Qt.Key_1 <= key <= Qt.Key_4:
            symbol_map = {
                Qt.Key_1: "$",
                Qt.Key_2: "£",
                Qt.Key_3: "€",
                Qt.Key_4: "¥",
            }
            self.select_currency(symbol_map[key])
            return

        # 9: flag for manual review
        if key == Qt.Key_9:
            self.flag_number()
            return

        # 0-8: type selection
        if Qt.Key_0 <= key <= Qt.Key_8:
            type_key = key - Qt.Key_0
            self.select_type(type_key)
            return

        # Enter/Space: accept
        if key in (Qt.Key_Return, Qt.Key_Space):
            self.accept_proposal()
            return

        # Left arrow: previous
        if key == Qt.Key_Left:
            self.previous_proposal()
            return

        # Right arrow: next
        if key == Qt.Key_Right:
            self.next_proposal()
            return

        # Backspace: skip (restore original)
        if key == Qt.Key_Backspace:
            self.select_type(0)
            return

        super().keyPressEvent(event)

    def get_proposals(self) -> List[Dict]:
        """Return the modified proposals for applying."""
        return self.proposals
