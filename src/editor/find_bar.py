"""Minimal VS Code-style find bar (Ctrl+F): next/previous, Esc closes."""

from PySide6 import QtCore, QtWidgets

from . import i18n
from .icons import SIZE_MENU, apply_icon
from .qt_text import install_text_context_menu


class FindBar(QtWidgets.QWidget):
    """Thin search strip. Search itself lives in MainWindow."""

    findRequested = QtCore.Signal(str, int)  # (text, direction +1/-1)
    replaceRequested = QtCore.Signal(str, bool)  # (text, replace_all)
    optionsChanged = QtCore.Signal(bool, bool)  # (match_case, whole_word)
    closed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(4)
        self._input = QtWidgets.QLineEdit(self)
        self._input.setPlaceholderText(i18n.tr('find.placeholder'))
        self._input.setClearButtonEnabled(True)
        install_text_context_menu(self._input)
        row.addWidget(self._input, 1)

        self._count = QtWidgets.QLabel('', self)
        row.addWidget(self._count)

        prev_button = QtWidgets.QPushButton(self)
        prev_button.setFlat(True)
        prev_button.setToolTip(i18n.tr('find.prev_tip'))
        prev_button.setAccessibleName(i18n.tr('find.prev_tip'))
        apply_icon(prev_button, 'find-prev', SIZE_MENU)
        prev_button.setMinimumSize(28, 28)
        prev_button.clicked.connect(lambda: self._emit(-1))
        row.addWidget(prev_button)

        next_button = QtWidgets.QPushButton(self)
        next_button.setFlat(True)
        next_button.setToolTip(i18n.tr('find.next_tip'))
        next_button.setAccessibleName(i18n.tr('find.next_tip'))
        apply_icon(next_button, 'find-next', SIZE_MENU)
        next_button.setMinimumSize(28, 28)
        next_button.clicked.connect(lambda: self._emit(1))
        row.addWidget(next_button)

        close_button = QtWidgets.QPushButton(self)
        close_button.setFlat(True)
        close_button.setToolTip(i18n.tr('find.close_tip'))
        close_button.setAccessibleName(i18n.tr('find.close_tip'))
        apply_icon(close_button, 'find-close', SIZE_MENU)
        close_button.setMinimumSize(28, 28)
        close_button.clicked.connect(self.hide_bar)
        row.addWidget(close_button)
        layout.addLayout(row)

        # Replace row: hidden until the replace button is toggled.
        replace_row = QtWidgets.QHBoxLayout()
        replace_row.setSpacing(4)
        self._replace_input = QtWidgets.QLineEdit(self)
        self._replace_input.setPlaceholderText(
            i18n.tr('find.replace_placeholder'))
        self._replace_input.setClearButtonEnabled(True)
        install_text_context_menu(self._replace_input)
        replace_row.addWidget(self._replace_input, 1)

        self._replace_button = QtWidgets.QPushButton(
            i18n.tr('find.replace'), self)
        self._replace_button.setToolTip(i18n.tr('find.replace_tip'))
        self._replace_button.setAccessibleName(i18n.tr('find.replace'))
        apply_icon(self._replace_button, 'replace', SIZE_MENU)
        self._replace_button.clicked.connect(
            lambda: self.replaceRequested.emit(
                self._replace_input.text(), False))
        replace_row.addWidget(self._replace_button)

        self._replace_all_button = QtWidgets.QPushButton(
            i18n.tr('find.replace_all'), self)
        self._replace_all_button.setToolTip(i18n.tr('find.replace_all_tip'))
        self._replace_all_button.setAccessibleName(
            i18n.tr('find.replace_all'))
        apply_icon(self._replace_all_button, 'replace-all', SIZE_MENU)
        self._replace_all_button.clicked.connect(
            lambda: self.replaceRequested.emit(
                self._replace_input.text(), True))
        replace_row.addWidget(self._replace_all_button)

        self._match_case_button = QtWidgets.QPushButton(self)
        self._match_case_button.setFlat(True)
        self._match_case_button.setCheckable(True)
        self._match_case_button.setToolTip(i18n.tr('find.match_case_tip'))
        self._match_case_button.setAccessibleName(i18n.tr('find.match_case'))
        apply_icon(self._match_case_button, 'match-case', SIZE_MENU)
        self._match_case_button.setMinimumSize(28, 28)
        self._match_case_button.toggled.connect(self._on_options_toggled)
        replace_row.addWidget(self._match_case_button)

        self._whole_word_button = QtWidgets.QPushButton(self)
        self._whole_word_button.setFlat(True)
        self._whole_word_button.setCheckable(True)
        self._whole_word_button.setToolTip(i18n.tr('find.whole_word_tip'))
        self._whole_word_button.setAccessibleName(i18n.tr('find.whole_word'))
        apply_icon(self._whole_word_button, 'whole-word', SIZE_MENU)
        self._whole_word_button.setMinimumSize(28, 28)
        self._whole_word_button.toggled.connect(self._on_options_toggled)
        replace_row.addWidget(self._whole_word_button)

        self._replace_row = replace_row
        replace_widget = QtWidgets.QWidget(self)
        replace_widget.setLayout(replace_row)
        layout.addWidget(replace_widget)
        self._replace_widget = replace_widget
        replace_widget.setVisible(False)

        # A small replace toggle in the first row opens the second row.
        self._replace_toggle = QtWidgets.QPushButton(self)
        self._replace_toggle.setFlat(True)
        self._replace_toggle.setCheckable(True)
        self._replace_toggle.setToolTip(i18n.tr('find.replace_tip'))
        self._replace_toggle.setAccessibleName(i18n.tr('find.replace'))
        apply_icon(self._replace_toggle, 'replace', SIZE_MENU)
        self._replace_toggle.setMinimumSize(28, 28)
        self._replace_toggle.toggled.connect(
            lambda checked: self._replace_widget.setVisible(checked))
        row.addWidget(self._replace_toggle)

        self._prev_button = prev_button
        self._next_button = next_button
        self._close_button = close_button
        self._input.textChanged.connect(lambda: self._emit(0))
        self._input.returnPressed.connect(lambda: self._emit(1))
        self.setVisible(False)

    def _on_options_toggled(self, _checked=False):
        # MainWindow re-runs the search on optionsChanged; emitting
        # findRequested here too would advance twice.
        self.optionsChanged.emit(self._match_case_button.isChecked(),
                                 self._whole_word_button.isChecked())

    @property
    def match_case(self):
        return self._match_case_button.isChecked()

    @property
    def whole_word(self):
        return self._whole_word_button.isChecked()

    def retranslate_ui(self):
        self._input.setPlaceholderText(i18n.tr('find.placeholder'))
        self._prev_button.setToolTip(i18n.tr('find.prev_tip'))
        self._prev_button.setAccessibleName(i18n.tr('find.prev_tip'))
        self._next_button.setToolTip(i18n.tr('find.next_tip'))
        self._next_button.setAccessibleName(i18n.tr('find.next_tip'))
        self._close_button.setToolTip(i18n.tr('find.close_tip'))
        self._close_button.setAccessibleName(i18n.tr('find.close_tip'))
        self._replace_input.setPlaceholderText(
            i18n.tr('find.replace_placeholder'))
        self._replace_button.setText(i18n.tr('find.replace'))
        self._replace_button.setToolTip(i18n.tr('find.replace_tip'))
        self._replace_all_button.setText(i18n.tr('find.replace_all'))
        self._replace_all_button.setToolTip(i18n.tr('find.replace_all_tip'))
        self._match_case_button.setToolTip(i18n.tr('find.match_case_tip'))
        self._match_case_button.setAccessibleName(i18n.tr('find.match_case'))
        self._whole_word_button.setToolTip(i18n.tr('find.whole_word_tip'))
        self._whole_word_button.setAccessibleName(i18n.tr('find.whole_word'))

    def show_bar(self, initial_text=''):
        if initial_text and initial_text != self._input.text():
            self._input.setText(initial_text)
        self.setVisible(True)
        self._input.setFocus()
        self._input.selectAll()

    def hide_bar(self):
        self.setVisible(False)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.hide_bar()
            event.accept()
            return
        super().keyPressEvent(event)

    def set_match_count(self, index, total):
        """Update the 'i of n' label (either may be 0)."""
        if total:
            self._count.setText(
                i18n.tr('find.count', index=index, total=total))
        else:
            self._count.setText(i18n.tr('find.count_zero'))

    def _emit(self, direction):
        self.findRequested.emit(self._input.text(), direction)
