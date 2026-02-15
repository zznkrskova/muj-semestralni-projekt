from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QComboBox, QCheckBox,
    QSpinBox, QHBoxLayout, QVBoxLayout, QGroupBox, QMessageBox, QToolButton
)

from database import get_all_templates, delete_template
from logic import suggest_after_hours_difficulty


class BaseActivityDialog(QDialog):
    """Společný základ pro dialogy aktivit (čas, náročnost, odpočinek)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._difficulty_manual = False

    def setup_template_selector(self, layout):
        layout.addWidget(QLabel("Šablona:"))
        self.template_combo = QComboBox()
        self.template_combo.addItem("-- Bez šablony --")
        self._load_templates()
        self.template_combo.currentIndexChanged.connect(self._on_template_selected)
        row = QHBoxLayout()
        row.addWidget(self.template_combo)

        self.delete_template_btn = QToolButton()
        self.delete_template_btn.setText("✖")
        self.delete_template_btn.setToolTip("Smazat vybranou šablonu")
        self.delete_template_btn.setEnabled(False)
        self.delete_template_btn.clicked.connect(self._on_delete_template_clicked)
        row.addWidget(self.delete_template_btn)

        layout.addLayout(row)

    def _load_templates(self):
        self.template_combo.clear()
        self.template_combo.addItem("-- Bez šablony --")
        templates = get_all_templates()
        for t in templates:
            self.template_combo.addItem(t[1], t)
        if hasattr(self, "delete_template_btn"):
            self.delete_template_btn.setEnabled(False)

    def _on_template_selected(self, index):
        if hasattr(self, "delete_template_btn"):
            self.delete_template_btn.setEnabled(index > 0)
        if index == 0:
            return
        template = self.template_combo.currentData()
        if template:
            self.apply_template(template)

    def apply_template(self, template):
        self.name.setText(template[1])
        self.category.setCurrentText(template[2])
        self.start_h.setValue(template[3])
        self.start_m.setValue(template[4])
        self.end_h.setValue(template[5])
        self.end_m.setValue(template[6])
        self.difficulty.setCurrentText(str(template[7]))
        self.all_day_cb.setChecked(template[8] == 1)
        self._difficulty_manual = False
        self.apply_auto_difficulty()

    def _on_delete_template_clicked(self):
        index = self.template_combo.currentIndex()
        if index <= 0:
            return
        template = self.template_combo.currentData()
        if not template:
            return
        reply = QMessageBox.question(
            self,
            "Smazat šablonu",
            f"Opravdu smazat šablonu '{template[1]}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_template(template[0])
            self._load_templates()

    def setup_common_fields(self, layout, initial=None):
        if getattr(self, "_common_fields_built", False):
            return
        self._common_fields_built = True
        initial = initial or {}

        layout.addWidget(QLabel("Název:"))
        self.name = QLineEdit(initial.get("name", ""))
        layout.addWidget(self.name)

        layout.addWidget(QLabel("Kategorie:"))
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(["Práce", "Studium", "Cvičení", "Volný čas", "Jiné"])
        if initial.get("category"):
            self.category.setCurrentText(initial["category"])
        self.category.currentTextChanged.connect(self.apply_auto_difficulty)
        layout.addWidget(self.category)

        self.all_day_cb = QCheckBox("Celodenní aktivita")
        self.all_day_cb.setChecked(bool(initial.get("all_day", False)))
        self.all_day_cb.stateChanged.connect(self.toggle_time)
        layout.addWidget(self.all_day_cb)

        layout.addWidget(QLabel("Čas začátku:"))
        time_start = QHBoxLayout()
        self.start_h = QSpinBox()
        self.start_h.setRange(0, 23)
        self.start_h.setValue(initial.get("sh", 0))
        self.start_m = QSpinBox()
        self.start_m.setRange(0, 59)
        self.start_m.setValue(initial.get("sm", 0))
        self.start_h.valueChanged.connect(self.apply_auto_difficulty)
        self.start_m.valueChanged.connect(self.apply_auto_difficulty)
        time_start.addWidget(QLabel("Hod:"))
        time_start.addWidget(self.start_h)
        time_start.addWidget(QLabel("Min:"))
        time_start.addWidget(self.start_m)
        layout.addLayout(time_start)

        layout.addWidget(QLabel("Čas konce:"))
        time_end = QHBoxLayout()
        self.end_h = QSpinBox()
        self.end_h.setRange(0, 23)
        self.end_h.setValue(initial.get("eh", 0))
        self.end_m = QSpinBox()
        self.end_m.setRange(0, 59)
        self.end_m.setValue(initial.get("em", 0))
        time_end.addWidget(QLabel("Hod:"))
        time_end.addWidget(self.end_h)
        time_end.addWidget(QLabel("Min:"))
        time_end.addWidget(self.end_m)
        layout.addLayout(time_end)

        layout.addWidget(QLabel("Náročnost (1-5):"))
        self.difficulty = QComboBox()
        self.difficulty.addItems(["1", "2", "3", "4", "5"])
        self.difficulty.setCurrentText(str(initial.get("difficulty", 1)))
        self.difficulty.currentTextChanged.connect(self.on_difficulty_changed)
        layout.addWidget(self.difficulty)

        self.toggle_time()

    def setup_rest_group(self, layout, rest_type=None, rest_amount=0):
        self.rest_group = QGroupBox("Odpočinek - vyberte typ a intenzitu")
        rest_layout = QVBoxLayout()

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Typ odpočinku:"))
        self.rest_type_combo = QComboBox()
        self.rest_type_combo.addItems(["Bez odpočinku", "Fyzický", "Psychický"])

        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("Intenzita odpočinku:"))
        self.rest_amount_spin = QSpinBox()
        self.rest_amount_spin.setRange(1, 5)
        self.rest_amount_spin.setValue(rest_amount if rest_amount > 0 else 1)
        amount_layout.addWidget(self.rest_amount_spin)

        if rest_type == "physical":
            initial_text = "Fyzický"
        elif rest_type == "mental":
            initial_text = "Psychický"
        else:
            initial_text = "Bez odpočinku"

        self.rest_type_combo.blockSignals(True)
        self.rest_type_combo.setCurrentText(initial_text)
        self.rest_type_combo.blockSignals(False)
        self.rest_type_combo.currentTextChanged.connect(self.on_rest_type_changed)
        self.on_rest_type_changed()

        type_layout.addWidget(self.rest_type_combo)
        rest_layout.addLayout(type_layout)
        amount_layout.addWidget(self.rest_amount_spin)
        rest_layout.addLayout(amount_layout)

        self.rest_group.setLayout(rest_layout)
        layout.addWidget(self.rest_group)

    def on_difficulty_changed(self):
        self._difficulty_manual = True

    def apply_auto_difficulty(self):
        if self._difficulty_manual:
            return
        suggested = suggest_after_hours_difficulty(
            self.category.currentText(),
            self.start_h.value(),
            self.start_m.value(),
            int(self.difficulty.currentText())
        )
        self.difficulty.blockSignals(True)
        self.difficulty.setCurrentText(str(suggested))
        self.difficulty.blockSignals(False)

    def toggle_time(self):
        enabled = not self.all_day_cb.isChecked()
        self.start_h.setEnabled(enabled)
        self.start_m.setEnabled(enabled)
        self.end_h.setEnabled(enabled)
        self.end_m.setEnabled(enabled)

    def on_rest_type_changed(self):
        has_rest = self.rest_type_combo.currentText() != "Bez odpočinku"
        self.rest_amount_spin.setEnabled(has_rest)

    def get_time_values(self):
        if self.all_day_cb.isChecked():
            return 0, 0, 23, 59
        return self.start_h.value(), self.start_m.value(), self.end_h.value(), self.end_m.value()

    def get_rest_values(self):
        is_rest = 0
        rest_type = None
        rest_amount = 0

        selected_rest = self.rest_type_combo.currentText()
        if selected_rest == "Fyzický":
            is_rest = 1
            rest_type = "physical"
            rest_amount = self.rest_amount_spin.value()
        elif selected_rest == "Psychický":
            is_rest = 1
            rest_type = "mental"
            rest_amount = self.rest_amount_spin.value()

        return is_rest, rest_type, rest_amount

    def _is_time_range_valid(self):
        if self.all_day_cb.isChecked():
            return True
        start = self.start_h.value() * 60 + self.start_m.value()
        end = self.end_h.value() * 60 + self.end_m.value()
        return end > start

    def accept(self):
        if not self._is_time_range_valid():
            QMessageBox.warning(self, "Neplatný čas", "Čas konce musí být později než čas začátku.")
            return
        super().accept()
