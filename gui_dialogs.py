from PySide6.QtWidgets import (
    QDialog, QLabel, QSpinBox, QComboBox, QLineEdit, QCheckBox,
    QDateEdit, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
)
from PySide6.QtCore import QDate

from gui_base import BaseActivityDialog
from database import get_flag, get_activity_by_id, get_activity_note, delete_activity_note
from logic import get_date_range, activity_applies_to_day


def _clear_checkbox(checkbox):
    checkbox.blockSignals(True)
    checkbox.setChecked(False)
    checkbox.blockSignals(False)


def _apply_weekend_filter(dates, weekdays_only, weekends_only):
    if weekdays_only:
        return [d for d in dates if QDate.fromString(d, "yyyy-MM-dd").dayOfWeek() <= 5]
    if weekends_only:
        return [d for d in dates if QDate.fromString(d, "yyyy-MM-dd").dayOfWeek() >= 6]
    return dates

def _add_ok_cancel_row(layout, ok_text, ok_handler, cancel_handler):
    btn_ok = QPushButton(ok_text)
    btn_cancel = QPushButton("Zrušit")
    btns = QHBoxLayout()
    btns.addWidget(btn_ok)
    btns.addWidget(btn_cancel)
    layout.addLayout(btns)
    btn_ok.clicked.connect(ok_handler)
    btn_cancel.clicked.connect(cancel_handler)


class AddActivityDialog(BaseActivityDialog):
    """Dialog pro přidávání jednorázové aktivity"""
    def __init__(self, parent=None, date_str=""):
        super().__init__(parent)
        self.setWindowTitle("Přidat aktivitu")
        layout = QVBoxLayout()

        self.setup_template_selector(layout)
        self.setup_common_fields(layout)
        self.setup_rest_group(layout)

        layout.addWidget(QLabel("Datum:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.fromString(date_str, "yyyy-MM-dd") if date_str else QDate.currentDate())
        layout.addWidget(self.date_edit)

        _add_ok_cancel_row(layout, "Přidat", self.accept, self.reject)

        self.setLayout(layout)
        self.apply_auto_difficulty()

    def get_data(self):
        sh, sm, eh, em = self.get_time_values()
        is_rest, rest_type, rest_amount = self.get_rest_values()

        return {
            "name": self.name.text(),
            "category": self.category.currentText(),
            "sh": sh,
            "sm": sm,
            "eh": eh,
            "em": em,
            "difficulty": int(self.difficulty.currentText()),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "is_rest": is_rest,
            "rest_type": rest_type,
            "rest_amount": rest_amount
        }


class AddRecurringActivityDialog(BaseActivityDialog):
    """Dialog pro přidávání dlouhodobé aktivity"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Přidat dlouhodobou aktivitu")
        layout = QVBoxLayout()

        self.setup_template_selector(layout)
        self.setup_common_fields(layout)

        layout.addWidget(QLabel("Opakování:"))
        layout.addWidget(QLabel("Dny v týdnu:"))
        days_layout = QHBoxLayout()
        self.day_checks = {}
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            cb = QCheckBox(day)
            self.day_checks[day] = cb
            days_layout.addWidget(cb)
        layout.addLayout(days_layout)

        # NOVÉ: rychlé volby
        quick_layout = QHBoxLayout()
        self.weekdays_only = QCheckBox("Jen všední dny")
        self.weekends_only = QCheckBox("Jen víkendy")
        self.weekdays_only.stateChanged.connect(self.apply_quick_days)
        self.weekends_only.stateChanged.connect(self.apply_quick_days)
        quick_layout.addWidget(self.weekdays_only)
        quick_layout.addWidget(self.weekends_only)
        layout.addLayout(quick_layout)

        self.yearly_cb = QCheckBox("Opakovat každý rok (např. narozeniny)")
        self.yearly_cb.stateChanged.connect(self.toggle_yearly)
        layout.addWidget(self.yearly_cb)

        layout.addWidget(QLabel("Datum (měsíc a den):"))
        self.recurring_date = QDateEdit()
        self.recurring_date.setCalendarPopup(True)
        self.recurring_date.setDate(QDate.currentDate())
        self.recurring_date.setEnabled(False)
        layout.addWidget(self.recurring_date)

        self.setup_rest_group(layout)

        _add_ok_cancel_row(layout, "Přidat", self.accept, self.reject)

        self.setLayout(layout)

        self.apply_auto_difficulty()

    def apply_quick_days(self):
        if self.weekdays_only.isChecked():
            _clear_checkbox(self.weekends_only)
            for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
                self.day_checks[d].setChecked(True)
            for d in ["Sat", "Sun"]:
                self.day_checks[d].setChecked(False)

        elif self.weekends_only.isChecked():
            _clear_checkbox(self.weekdays_only)
            for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
                self.day_checks[d].setChecked(False)
            for d in ["Sat", "Sun"]:
                self.day_checks[d].setChecked(True)

    def toggle_yearly(self):
        self.recurring_date.setEnabled(self.yearly_cb.isChecked())

    def get_data(self):
        sh, sm, eh, em = self.get_time_values()

        days = ",".join([day for day, cb in self.day_checks.items() if cb.isChecked()])
        rec_date = self.recurring_date.date().toString("MM-dd") if self.yearly_cb.isChecked() else None

        is_rest, rest_type, rest_amount = self.get_rest_values()

        return {
            "name": self.name.text(),
            "category": self.category.currentText(),
            "sh": sh,
            "sm": sm,
            "eh": eh,
            "em": em,
            "difficulty": int(self.difficulty.currentText()),
            "recurring_days": days if days else None,
            "recurring_date": rec_date,
            "is_rest": is_rest,
            "rest_type": rest_type,
            "rest_amount": rest_amount
        }


class AddMultipleDaysDialog(BaseActivityDialog):
    """Dialog pro přidání aktivity na více dní najednou"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Přidat aktivitu na více dní")
        layout = QVBoxLayout()

        self.setup_template_selector(layout)
        self.setup_common_fields(layout)

        layout.addWidget(QLabel("Vyberte rozsah datumů:"))
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(QLabel("Od:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("Do:"))
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # NOVÉ: filtr dnů
        filter_layout = QHBoxLayout()
        self.weekdays_only = QCheckBox("Jen všední dny")
        self.weekends_only = QCheckBox("Jen víkendy")
        self.weekdays_only.stateChanged.connect(self.on_filter_changed)
        self.weekends_only.stateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.weekdays_only)
        filter_layout.addWidget(self.weekends_only)
        layout.addLayout(filter_layout)

        self.setup_rest_group(layout)

        _add_ok_cancel_row(layout, "Přidat", self.accept, self.reject)

        self.setLayout(layout)

        self.apply_auto_difficulty()

    def on_filter_changed(self):
        if self.weekdays_only.isChecked():
            _clear_checkbox(self.weekends_only)
        elif self.weekends_only.isChecked():
            _clear_checkbox(self.weekdays_only)

    def get_data(self):
        sh, sm, eh, em = self.get_time_values()

        start_str = self.start_date.date().toString("yyyy-MM-dd")
        end_str = self.end_date.date().toString("yyyy-MM-dd")
        dates = get_date_range(start_str, end_str)

        # NOVÉ: filtr dle všední/víkend
        dates = _apply_weekend_filter(dates, self.weekdays_only.isChecked(), self.weekends_only.isChecked())

        is_rest, rest_type, rest_amount = self.get_rest_values()

        return {
            "name": self.name.text(),
            "category": self.category.currentText(),
            "sh": sh,
            "sm": sm,
            "eh": eh,
            "em": em,
            "difficulty": int(self.difficulty.currentText()),
            "dates": dates,
            "is_rest": is_rest,
            "rest_type": rest_type,
            "rest_amount": rest_amount
        }


class CreateTemplateDialog(QDialog):
    """Dialog pro vytvoření šablony aktivity"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vytvořit šablonu aktivity")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Název šablony:"))
        self.name = QLineEdit()
        layout.addWidget(self.name)

        layout.addWidget(QLabel("Kategorie:"))
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(["Práce", "Studium", "Cvičení", "Volný čas", "Jiné"])
        layout.addWidget(self.category)

        self.all_day_cb = QCheckBox("Celodenní aktivita")
        self.all_day_cb.stateChanged.connect(self.toggle_time)
        layout.addWidget(self.all_day_cb)

        layout.addWidget(QLabel("Čas začátku:"))
        time_start = QHBoxLayout()
        self.start_h = QSpinBox()
        self.start_h.setRange(0, 23)
        self.start_m = QSpinBox()
        self.start_m.setRange(0, 59)
        time_start.addWidget(QLabel("Hod:"))
        time_start.addWidget(self.start_h)
        time_start.addWidget(QLabel("Min:"))
        time_start.addWidget(self.start_m)
        layout.addLayout(time_start)

        layout.addWidget(QLabel("Čas konce:"))
        time_end = QHBoxLayout()
        self.end_h = QSpinBox()
        self.end_h.setRange(0, 23)
        self.end_m = QSpinBox()
        self.end_m.setRange(0, 59)
        time_end.addWidget(QLabel("Hod:"))
        time_end.addWidget(self.end_h)
        time_end.addWidget(QLabel("Min:"))
        time_end.addWidget(self.end_m)
        layout.addLayout(time_end)

        layout.addWidget(QLabel("Náročnost (1-5):"))
        self.difficulty = QComboBox()
        self.difficulty.addItems(["1", "2", "3", "4", "5"])
        layout.addWidget(self.difficulty)

        layout.addWidget(QLabel("Typ zátěže:"))
        self.load_type = QComboBox()
        self.load_type.addItems(["Psychická", "Fyzická"])
        layout.addWidget(self.load_type)

        _add_ok_cancel_row(layout, "Vytvořit", self._on_accept, self.reject)

        self.setLayout(layout)

    def toggle_time(self):
        enabled = not self.all_day_cb.isChecked()
        self.start_h.setEnabled(enabled)
        self.start_m.setEnabled(enabled)
        self.end_h.setEnabled(enabled)
        self.end_m.setEnabled(enabled)

    def _is_time_range_valid(self):
        if self.all_day_cb.isChecked():
            return True
        start = self.start_h.value() * 60 + self.start_m.value()
        end = self.end_h.value() * 60 + self.end_m.value()
        return end > start

    def _on_accept(self):
        if not self._is_time_range_valid():
            QMessageBox.warning(self, "Neplatný čas", "Čas konce musí být později než čas začátku.")
            return
        self.accept()

    def get_data(self):
        if self.all_day_cb.isChecked():
            sh, sm, eh, em = 0, 0, 23, 59
            all_day = 1
        else:
            sh = self.start_h.value()
            sm = self.start_m.value()
            eh = self.end_h.value()
            em = self.end_m.value()
            all_day = 0

        return {
            "name": self.name.text(),
            "category": self.category.currentText(),
            "sh": sh,
            "sm": sm,
            "eh": eh,
            "em": em,
            "difficulty": int(self.difficulty.currentText()),
            "all_day": all_day,
            "load_type": "mental" if self.load_type.currentIndex() == 0 else "physical"
        }


class AddNoteDialog(QDialog):
    """Dialog pro přidání/úpravu poznámky k aktivitě"""
    def __init__(self, parent=None, activity=None, date=None):
        super().__init__(parent)
        self.setWindowTitle(f"Poznámka k aktivitě: {activity[1]}")
        self.activity = activity
        self.date = date
        self.deleted = False

        layout = QVBoxLayout()

        layout.addWidget(QLabel(f"Aktivita: {activity[1]}"))
        layout.addWidget(QLabel(f"Datum: {date}"))

        layout.addWidget(QLabel("Poznámka:"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Zadejte poznámku...")

        # Načti existující poznámku
        existing_note = get_activity_note(activity[0], date)
        if existing_note:
            self.note_edit.setText(existing_note)

        layout.addWidget(self.note_edit)

        btn_save = QPushButton("Uložit")
        btn_delete = QPushButton("Smazat poznámku")
        btn_cancel = QPushButton("Zrušit")
        btns = QHBoxLayout()
        btns.addWidget(btn_save)
        btns.addWidget(btn_delete)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        self.setLayout(layout)
        btn_save.clicked.connect(self.accept)
        btn_delete.clicked.connect(self.delete_note)
        btn_cancel.clicked.connect(self.reject)

    def delete_note(self):
        self.deleted = True
        self.note_edit.clear()
        delete_activity_note(self.activity[0], self.date)
        self.accept()

    def get_note(self):
        return self.note_edit.text()


class SelectDaysDialog(QDialog):
    """Dialog pro výběr konkrétních dnů"""
    def __init__(self, parent=None, activity=None, current_date=None, filter_by_activity=True):
        super().__init__(parent)
        self.setWindowTitle("Vyberte dny")
        self.activity = activity
        self.selected_dates = []
        self.filter_by_activity = filter_by_activity
        self.on_specific_day_changed = self._on_specific_day_changed

        layout = QVBoxLayout()

        layout.addWidget(QLabel(f"Vyberte dny pro aktivitu: {activity[1]}"))
        layout.addWidget(QLabel("Vyberte rozsah datumů:"))

        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate() if not current_date else QDate.fromString(current_date, "yyyy-MM-dd"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addDays(30))
        date_layout.addWidget(QLabel("Od:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("Do:"))
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # Filtry - rychlé volby
        filter_layout = QHBoxLayout()
        self.weekdays_only = QCheckBox("Jen všední dny")
        self.weekends_only = QCheckBox("Jen víkendy")
        self.weekdays_only.stateChanged.connect(self.on_filter_changed)
        self.weekends_only.stateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.weekdays_only)
        filter_layout.addWidget(self.weekends_only)
        layout.addLayout(filter_layout)

        # Výběr konkrétních dnů v týdnu
        layout.addWidget(QLabel("Nebo vyberte konkrétní dny v týdnu:"))
        days_layout = QHBoxLayout()
        self.day_checks = {}
        for day_name, day_label in [
            ("Mon", "Po"), ("Tue", "Út"), ("Wed", "St"),
            ("Thu", "Čt"), ("Fri", "Pá"), ("Sat", "So"), ("Sun", "Ne")
        ]:
            cb = QCheckBox(day_label)
            self.day_checks[day_name] = cb
            cb.stateChanged.connect(self.on_specific_day_changed)
            days_layout.addWidget(cb)
        layout.addLayout(days_layout)

        _add_ok_cancel_row(layout, "Pokračovat", self.accept, self.reject)

        self.setLayout(layout)

    def on_filter_changed(self):
        if self.weekdays_only.isChecked():
            _clear_checkbox(self.weekends_only)
            # Vyčisti konkrétní dny
            for cb in self.day_checks.values():
                _clear_checkbox(cb)
        elif self.weekends_only.isChecked():
            _clear_checkbox(self.weekdays_only)
            # Vyčisti konkrétní dny
            for cb in self.day_checks.values():
                _clear_checkbox(cb)

    def _on_specific_day_changed(self):
        # Pokud je vybrán konkrétní den, zruš rychlé volby
        if any(cb.isChecked() for cb in self.day_checks.values()):
            self.weekdays_only.blockSignals(True)
            self.weekdays_only.setChecked(False)
            self.weekdays_only.blockSignals(False)
            self.weekends_only.blockSignals(True)
            self.weekends_only.setChecked(False)
            self.weekends_only.blockSignals(False)

    def on_specific_day_changed(self):
        self._on_specific_day_changed()

    def get_dates(self):
        start_str = self.start_date.date().toString("yyyy-MM-dd")
        end_str = self.end_date.date().toString("yyyy-MM-dd")
        dates = get_date_range(start_str, end_str)

        # Aplikuj filtry
        if self.weekdays_only.isChecked() or self.weekends_only.isChecked():
            dates = _apply_weekend_filter(dates, self.weekdays_only.isChecked(), self.weekends_only.isChecked())
        else:
            # Zkontroluj, zda jsou vybrané konkrétní dny
            selected_days = [day for day, cb in self.day_checks.items() if cb.isChecked()]
            if selected_days:
                # Filtruj podle vybraných dnů (Mon=1, Tue=2, ..., Sun=7)
                day_to_num = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 7}
                selected_nums = [day_to_num[d] for d in selected_days]
                dates = [d for d in dates if QDate.fromString(d, "yyyy-MM-dd").dayOfWeek() in selected_nums]

        # Filtruj jen dny, kde se aktivita zobrazuje
        if self.filter_by_activity and self.activity:
            dates = [d for d in dates if activity_applies_to_day(self.activity, d)]

        return dates


class ConflictResolutionDialog(QDialog):
    """Dialog pro řešení konfliktu mezi aktivitami"""
    def __init__(self, parent=None, new_activity=None, conflicting_activities=None):
        super().__init__(parent)
        self.setWindowTitle("Konflikt v plánu")
        self.new_activity = new_activity
        self.conflicting_activities = conflicting_activities or []
        self.choice = None

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Nová aktivita se protíná s existující:"))

        for act in self.conflicting_activities:
            info = f"{act[1]} ({act[3]:02d}:{act[4]:02d} - {act[5]:02d}:{act[6]:02d})"
            layout.addWidget(QLabel(f"• {info}"))

        layout.addWidget(QLabel("\nCo chcete udělat?"))

        btn_replace = QPushButton("Nahradit původní aktivitu novou")
        btn_replace.clicked.connect(lambda: self.set_choice("replace"))
        layout.addWidget(btn_replace)

        btn_keep = QPushButton("Nechat obě (překryv)")
        btn_keep.clicked.connect(lambda: self.set_choice("keep"))
        layout.addWidget(btn_keep)

        btn_shift_new = QPushButton("Posunout novou aktivitu později")
        btn_shift_new.clicked.connect(lambda: self.set_choice("shift_new"))
        layout.addWidget(btn_shift_new)

        btn_shift_old = QPushButton("Posunout původní aktivitu později")
        btn_shift_old.clicked.connect(lambda: self.set_choice("shift_existing"))
        layout.addWidget(btn_shift_old)

        btn_cancel = QPushButton("Nepřidávat novou")
        btn_cancel.clicked.connect(lambda: self.set_choice("cancel"))
        layout.addWidget(btn_cancel)

        self.setLayout(layout)
        self.setMinimumWidth(420)

    def set_choice(self, choice):
        self.choice = choice
        self.accept()


class EditActivityDialog(BaseActivityDialog):
    """Dialog pro úpravu aktivity"""
    def __init__(self, parent=None, activity_id=None, is_recurring_instance=False):
        super().__init__(parent)
        self.setWindowTitle("Upravit aktivitu")
        self.activity_id = activity_id
        self.is_recurring_instance = is_recurring_instance

        activity = get_activity_by_id(activity_id)
        if not activity:
            return

        layout = QVBoxLayout()

        is_all_day = (activity[3] == 0 and activity[4] == 0 and activity[5] == 23 and activity[6] == 59)
        initial = {
            "name": activity[1],
            "category": activity[2],
            "sh": activity[3],
            "sm": activity[4],
            "eh": activity[5],
            "em": activity[6],
            "difficulty": activity[7],
            "all_day": is_all_day
        }
        self.setup_common_fields(layout, initial)

        layout.addWidget(QLabel("Datum:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        if activity[8]:
            self.date_edit.setDate(QDate.fromString(activity[8], "yyyy-MM-dd"))
        else:
            self.date_edit.setDate(QDate.currentDate())
        layout.addWidget(self.date_edit)

        rest_type = activity[15] if len(activity) > 15 else None
        rest_amount = activity[16] if len(activity) > 16 else 0
        self.setup_rest_group(layout, rest_type=rest_type, rest_amount=rest_amount)

        _add_ok_cancel_row(layout, "Uložit", self.accept, self.reject)

        self.setLayout(layout)

        self.apply_auto_difficulty()

    def get_data(self):
        sh, sm, eh, em = self.get_time_values()
        is_rest, rest_type, rest_amount = self.get_rest_values()

        return {
            "name": self.name.text(),
            "category": self.category.currentText(),
            "sh": sh,
            "sm": sm,
            "eh": eh,
            "em": em,
            "difficulty": int(self.difficulty.currentText()),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "is_rest": is_rest,
            "rest_type": rest_type,
            "rest_amount": rest_amount
        }


class FirstRunDialog(QDialog):
    """Dialog při prvním spuštění pro nastavení cílů"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vítejte v plánovači!")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<b>Nastavte si cílové zátěže:</b>"))

        layout.addWidget(QLabel("Fyzická zátěž (min–max):"))
        phys_layout = QHBoxLayout()
        self.phys_min = QSpinBox()
        self.phys_min.setRange(0, 50)
        self.phys_min.setValue(3)
        self.phys_max = QSpinBox()
        self.phys_max.setRange(0, 50)
        self.phys_max.setValue(6)
        phys_layout.addWidget(self.phys_min)
        phys_layout.addWidget(QLabel("–"))
        phys_layout.addWidget(self.phys_max)
        layout.addLayout(phys_layout)

        layout.addWidget(QLabel("Psychická zátěž (min–max):"))
        ment_layout = QHBoxLayout()
        self.ment_min = QSpinBox()
        self.ment_min.setRange(0, 50)
        self.ment_min.setValue(4)
        self.ment_max = QSpinBox()
        self.ment_max.setRange(0, 50)
        self.ment_max.setValue(8)
        ment_layout.addWidget(self.ment_min)
        ment_layout.addWidget(QLabel("–"))
        ment_layout.addWidget(self.ment_max)
        layout.addLayout(ment_layout)

        btn_ok = QPushButton("Uložit")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

        self.setLayout(layout)

    def get_data(self):
        return {
            "phys_min": self.phys_min.value(),
            "phys_max": self.phys_max.value(),
            "ment_min": self.ment_min.value(),
            "ment_max": self.ment_max.value()
        }


class LoadSettingsDialog(QDialog):
    """Dialog pro úpravu cílů zátěže"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nastavení cílových zátěží")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Fyzická zátěž (min–max):"))
        phys_layout = QHBoxLayout()
        self.phys_min = QSpinBox()
        self.phys_min.setRange(0, 50)
        self.phys_min.setValue(int(get_flag("target_physical_min", "3")))
        self.phys_max = QSpinBox()
        self.phys_max.setRange(0, 50)
        self.phys_max.setValue(int(get_flag("target_physical_max", "6")))
        phys_layout.addWidget(self.phys_min)
        phys_layout.addWidget(QLabel("–"))
        phys_layout.addWidget(self.phys_max)
        layout.addLayout(phys_layout)

        layout.addWidget(QLabel("Psychická zátěž (min–max):"))
        ment_layout = QHBoxLayout()
        self.ment_min = QSpinBox()
        self.ment_min.setRange(0, 50)
        self.ment_min.setValue(int(get_flag("target_mental_min", "4")))
        self.ment_max = QSpinBox()
        self.ment_max.setRange(0, 50)
        self.ment_max.setValue(int(get_flag("target_mental_max", "8")))
        ment_layout.addWidget(self.ment_min)
        ment_layout.addWidget(QLabel("–"))
        ment_layout.addWidget(self.ment_max)
        layout.addLayout(ment_layout)

        btn_ok = QPushButton("Uložit")
        btn_cancel = QPushButton("Zrušit")
        btns = QHBoxLayout()
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        self.setLayout(layout)
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def get_data(self):
        return {
            "phys_min": self.phys_min.value(),
            "phys_max": self.phys_max.value(),
            "ment_min": self.ment_min.value(),
            "ment_max": self.ment_max.value()
        }
