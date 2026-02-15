from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
    QListWidget, QListWidgetItem, QMessageBox, QMenuBar,
    QDialog, QLabel, QSpinBox, QComboBox, QLineEdit, QCheckBox,
    QCalendarWidget, QDateEdit, QScrollArea, QMenu, QGroupBox
)
from PySide6.QtCore import Qt, QDate, QSize, Signal, QMimeData
from PySide6.QtGui import QColor, QFont, QDrag

from database import (
    add_activity, delete_activity, is_first_run, mark_initialized,
    update_activity, get_activity_by_id, add_template, get_all_templates,
    get_all_activities,
    set_flag, get_flag, get_template_by_name, get_activity_note,
    add_or_update_activity_note, delete_activity_note,
    add_activity_exception
)
from logic import (
    get_activities_for_day,
    check_conflicts, activity_applies_to_day,
    get_daily_recommendation, find_first_free_slot,
    shift_activity_time, is_all_day_activity,
    suggest_after_hours_difficulty,
    get_date_range, format_activity_time,
    add_activity_to_multiple_days
)
from gui_dialogs import (
    AddActivityDialog, AddRecurringActivityDialog,
    AddMultipleDaysDialog, CreateTemplateDialog, AddNoteDialog, SelectDaysDialog,
    ConflictResolutionDialog, EditActivityDialog, FirstRunDialog, LoadSettingsDialog
)
from gui_widgets import ActivityWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plánovač aktivit")
        self.setGeometry(100, 100, 900, 750)

        # OPRAVA: Menu musí být nastaveno PŘED central widgetem
        self.setup_menu()

        self.central = QWidget()
        self.layout = QVBoxLayout(self.central)
        self.setCentralWidget(self.central)

        # Kalendář s povoleným drop
        self.calendar = QCalendarWidget()
        self.calendar.setAcceptDrops(True)
        self.calendar.selectionChanged.connect(self.on_date_changed)

        self.calendar.dragEnterEvent = self.calendar_dragEnterEvent
        self.calendar.dropEvent = self.calendar_dropEvent
        self.calendar.dragMoveEvent = lambda e: e.acceptProposedAction()

        self.layout.addWidget(self.calendar)

        # Panel doporučení
        reco_container = QWidget()
        reco_container.setObjectName("recoContainer")
        reco_layout = QVBoxLayout(reco_container)
        reco_layout.setContentsMargins(10, 10, 10, 10)
        reco_layout.setSpacing(5)

        self.reco_title = QLabel("")
        self.reco_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        reco_layout.addWidget(self.reco_title)

        self.reco_text = QLabel("")
        self.reco_text.setStyleSheet("color: #666; font-size: 12px;")
        self.reco_text.setWordWrap(True)
        reco_layout.addWidget(self.reco_text)

        reco_container.setLayout(reco_layout)
        reco_container.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 5px;
                border: 1px solid #ddd;
            }
        """)
        self.layout.addWidget(reco_container)
        self.reco_container = reco_container  # Ulož referenci

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.activity_container = QWidget()
        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setSpacing(8)
        self.scroll.setWidget(self.activity_container)
        self.layout.addWidget(self.scroll)

        self.date = self.calendar.selectedDate().toString("yyyy-MM-dd")
        self.selected_activity = None
        self.selected_widget = None

        if is_first_run():
            dlg = FirstRunDialog(self)
            if dlg.exec():
                self._apply_target_settings(dlg.get_data())
            mark_initialized()
            self.add_recurring()

        self.refresh()

    def setup_menu(self):
        bar = QMenuBar(self)
        menu = bar.addMenu("≡ Menu")

        add_one = menu.addAction("+ Přidat jednorázovou aktivitu")
        add_one.triggered.connect(self.add_one_time)

        add_recurring = menu.addAction("+ Přidat dlouhodobou aktivitu")
        add_recurring.triggered.connect(self.add_recurring)

        add_multiple = menu.addAction("+ Přidat aktivitu na více dní")
        add_multiple.triggered.connect(self.add_multiple_days)

        menu.addSeparator()

        settings_load = menu.addAction("Nastavení cílových zátěží")
        settings_load.triggered.connect(self.open_load_settings)

        self.setMenuBar(bar)

    def update_recommendation(self):
        title, text = get_daily_recommendation(self.date)
        self.reco_title.setText(title)
        self.reco_text.setText(text)

        # Barevné zvýraznění podle doporučení
        if "Zvyšte aktivitu" in title:
            bg_color = "#FFE5E5"
            border_color = "#FF6B6B"
        elif "Doporučený odpočinek" in title or "Vyrovnat" in title:
            bg_color = "#FFF4E5"
            border_color = "#FFA500"
        else:
            bg_color = "#E5F5E5"
            border_color = "#52C41A"

        self.reco_title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {border_color};")
        self.reco_container.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 5px;
                border: 2px solid {border_color};
            }}
        """)

    def calendar_dropEvent(self, event):
        """Zachytí drop na kalendáři a zjistí datum pod kurzorem"""
        if not event.mimeData().hasText():
            event.ignore()
            return

        pos = event.pos()
        table_view = None
        for child in self.calendar.findChildren(QWidget):
            if child.__class__.__name__ == 'QTableView':
                table_view = child
                break

        if table_view:
            table_pos = table_view.mapFrom(self.calendar, pos)
            index = table_view.indexAt(table_pos)
            if index.isValid():
                date_variant = table_view.model().data(index, Qt.DisplayRole)
                if date_variant:
                    day = int(date_variant)
                    current_date = self.calendar.selectedDate()
                    new_qdate = QDate(current_date.year(), current_date.month(), day)
                    new_date = new_qdate.toString("yyyy-MM-dd") if new_qdate.isValid() else self.calendar.selectedDate().toString("yyyy-MM-dd")
                else:
                    new_date = self.calendar.selectedDate().toString("yyyy-MM-dd")
            else:
                new_date = self.calendar.selectedDate().toString("yyyy-MM-dd")
        else:
            new_date = self.calendar.selectedDate().toString("yyyy-MM-dd")

        data = event.mimeData().text().split("|")
        activity_id = int(data[0])
        is_recurring = int(data[1]) if len(data) > 1 else 0
        origin_date = data[2] if len(data) > 2 else ""

        activity = get_activity_by_id(activity_id)
        if not activity:
            event.ignore()
            return

        new_activity_dict = {
            "sh": activity[3],
            "sm": activity[4],
            "eh": activity[5],
            "em": activity[6]
        }
        existing_activities = get_activities_for_day(new_date)
        resolved = self._resolve_conflicts(new_activity_dict, existing_activities, new_date, replace_mode="delete_all")
        if not resolved:
            event.ignore()
            return
        new_activity_dict = resolved

        # ← TOTO JE VENKU ZE `if conflicts:` BLOKU
        final_sh = new_activity_dict["sh"]
        final_sm = new_activity_dict["sm"]
        final_eh = new_activity_dict["eh"]
        final_em = new_activity_dict["em"]

        if is_recurring:
            if origin_date and origin_date != new_date:
                add_activity_exception(activity_id, origin_date)
            load_type = activity[12] if len(activity) > 12 and activity[12] else 'mental'
            is_rest = activity[14] if len(activity) > 14 else 0
            rest_type = activity[15] if len(activity) > 15 else None
            rest_amount = activity[16] if len(activity) > 16 else 0
            add_activity(
                name=activity[1],
                category=activity[2],
                sh=final_sh,
                sm=final_sm,
                eh=final_eh,
                em=final_em,
                difficulty=activity[7],
                date=new_date,
                recurring=0,
                recurring_days=None,
                recurring_date=None,
                load_type=load_type,
                is_rest=is_rest,
                rest_type=rest_type,
                rest_amount=rest_amount
            )
        else:
            load_type = activity[12] if len(activity) > 12 and activity[12] else 'mental'
            update_activity(
                activity[0], activity[1], activity[2],
                final_sh, final_sm, final_eh, final_em,
                activity[7],
                date=new_date,
                load_type=load_type
            )

        self.calendar.setSelectedDate(QDate.fromString(new_date, "yyyy-MM-dd"))
        self.date = new_date
        self.refresh()
        event.acceptProposedAction()

    def ensure_template_from_activity(self, data):
        """Automaticky vytvoří šablonu z aktivity, pokud ještě neexistuje"""
        if not data.get("name"):
            return

        if get_template_by_name(data["name"]):
            return

        add_template(
            name=data["name"],
            category=data["category"],
            sh=data["sh"],
            sm=data["sm"],
            eh=data["eh"],
            em=data["em"],
            difficulty=data["difficulty"],
            all_day=1 if (data["sh"] == 0 and data["sm"] == 0 and data["eh"] == 23 and data["em"] == 59) else 0,
            load_type=data.get("load_type", "mental")
        )

    def add_one_time(self):
        dlg = AddActivityDialog(self, self.date)
        if dlg.exec():
            data = dlg.get_data()
            existing_activities = get_activities_for_day(data["date"])
            resolved = self._resolve_conflicts(data, existing_activities, data["date"], replace_mode="delete_one_time")
            if not resolved:
                return
            data = resolved

            self._add_activity_from_data(data, date=data["date"])
            self.ensure_template_from_activity(data)
            self.refresh()

    def add_recurring(self):
        dlg = AddRecurringActivityDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            self._add_activity_from_data(
                data,
                date=None,
                recurring=1,
                recurring_days=data.get("recurring_days"),
                recurring_date=data.get("recurring_date")
            )
            self.ensure_template_from_activity(data)
            self.refresh()

    def add_multiple_days(self):
        dlg = AddMultipleDaysDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            dates = data["dates"]

            # Nejprve zkontroluj všechny konfliktní dny
            days_with_conflicts = []
            for date_str in dates:
                existing_activities = get_activities_for_day(date_str)
                conflicts = check_conflicts(data, existing_activities, date_str)
                if conflicts:
                    days_with_conflicts.append((date_str, conflicts, existing_activities))

            # Pokud jsou konflikty, zeptej se uživatele jednou pro všechny dny
            global_choice = None
            if days_with_conflicts:
                # Ukažeme první konfliktní den jako příklad
                first_date, first_conflicts, _ = days_with_conflicts[0]

                msg = QMessageBox(self)
                msg.setWindowTitle(f"Konflikt nalezen ({len(days_with_conflicts)} dní)")
                msg.setText(f"Aktivita má konflikt v {len(days_with_conflicts)} dnech.\nPříklad z {first_date}:")
                info_text = "\n".join([f"• {c[1]} ({c[3]:02d}:{c[4]:02d}-{c[5]:02d}:{c[6]:02d})" for c in first_conflicts[:3]])
                if len(first_conflicts) > 3:
                    info_text += f"\n... a {len(first_conflicts)-3} další"
                msg.setInformativeText(info_text + "\n\nCo chcete udělat?")

                btn_replace = msg.addButton("Nahradit konfliktní aktivity", QMessageBox.AcceptRole)
                btn_shift = msg.addButton("Posunout novou aktivitu", QMessageBox.AcceptRole)
                btn_keep = msg.addButton("Nechat obě (překryv)", QMessageBox.AcceptRole)
                btn_cancel = msg.addButton("Zrušit", QMessageBox.RejectRole)
                msg.exec()

                if msg.clickedButton() == btn_cancel:
                    return
                elif msg.clickedButton() == btn_replace:
                    global_choice = "replace"
                elif msg.clickedButton() == btn_shift:
                    global_choice = "shift_new"
                elif msg.clickedButton() == btn_keep:
                    global_choice = "keep"

            # NEJPRVE zkontroluj, zda se aktivita vejde do všech dnů (při shift_new)
            if global_choice == "shift_new":
                impossible_days = []
                for date_str in dates:
                    existing_activities = get_activities_for_day(date_str)
                    conflicts = check_conflicts(data, existing_activities, date_str)
                    if conflicts:
                        last_end = max(c[5]*60 + c[6] for c in conflicts)
                        new_slot = find_first_free_slot(data, existing_activities, date_str, last_end)
                        if not new_slot:
                            impossible_days.append(date_str)

                # Pokud se nevejde do některých dnů, zruš celou operaci
                if impossible_days:
                    if len(impossible_days) == 1:
                        QMessageBox.information(self, "Aktivita se nevejde",
                            f"Do dne {impossible_days[0]} se nevejde volný čas pro aktivitu.\n\nAktivita nebude přidána do žádného dne.")
                    else:
                        days_text = ", ".join(impossible_days[:5])
                        if len(impossible_days) > 5:
                            days_text += f" a {len(impossible_days)-5} dalších"
                        QMessageBox.information(self, "Aktivita se nevejde",
                            f"Do {len(impossible_days)} dnů se nevejde volný čas pro aktivitu:\n{days_text}\n\nAktivita nebude přidána do žádného dne.")
                    return  # Zruš celou operaci

            # Zpracuj všechny dny podle globální volby
            for date_str in dates:
                existing_activities = get_activities_for_day(date_str)
                conflicts = check_conflicts(data, existing_activities, date_str)

                # Pokud JEN tento den má konflikt, použij globální volbu
                if conflicts and global_choice:
                    if global_choice == "replace":
                        self._apply_replace_conflicts(conflicts, date_str, replace_mode="delete_one_time")

                    elif global_choice == "shift_new":
                        last_end = max(c[5]*60 + c[6] for c in conflicts)
                        new_slot = find_first_free_slot(data, existing_activities, date_str, last_end)
                        # Použij upravený čas jen pro tento den
                        self._add_activity_from_data(
                            data,
                            date=date_str,
                            sh=new_slot["sh"],
                            sm=new_slot["sm"],
                            eh=new_slot["eh"],
                            em=new_slot["em"]
                        )
                        continue  # Přeskoč klasické přidání

                # Přidej aktivitu (pokud nebyla přidána v shift_new)
                if not (conflicts and global_choice == "shift_new"):
                    self._add_activity_from_data(data, date=date_str)

            self.ensure_template_from_activity(data)
            self.refresh()

    def create_template(self):
        dlg = CreateTemplateDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            add_template(
                name=data["name"],
                category=data["category"],
                sh=data["sh"],
                sm=data["sm"],
                eh=data["eh"],
                em=data["em"],
                difficulty=data["difficulty"],
                all_day=1 if (data["sh"] == 0 and data["sm"] == 0 and data["eh"] == 23 and data["em"] == 59) else 0,
                load_type=data.get("load_type", "mental")
            )
            QMessageBox.information(self, "Hotovo", f"Šablona '{data['name']}' byla vytvořena.")

    def open_load_settings(self):
        dlg = LoadSettingsDialog(self)
        if dlg.exec():
            self._apply_target_settings(dlg.get_data())
            QMessageBox.information(self, "Hotovo", "Nastavení uloženo.")
            self.update_recommendation()

    def _apply_target_settings(self, data):
        set_flag("target_physical_min", str(data["phys_min"]))
        set_flag("target_physical_max", str(data["phys_max"]))
        set_flag("target_mental_min", str(data["ment_min"]))
        set_flag("target_mental_max", str(data["ment_max"]))

    def _activity_kwargs_from_data(
        self,
        data,
        *,
        date=None,
        recurring=0,
        recurring_days=None,
        recurring_date=None,
        sh=None,
        sm=None,
        eh=None,
        em=None
    ):
        return {
            "name": data["name"],
            "category": data["category"],
            "sh": data["sh"] if sh is None else sh,
            "sm": data["sm"] if sm is None else sm,
            "eh": data["eh"] if eh is None else eh,
            "em": data["em"] if em is None else em,
            "difficulty": data["difficulty"],
            "date": date,
            "recurring": recurring,
            "recurring_days": recurring_days,
            "recurring_date": recurring_date,
            "load_type": data.get("load_type", "mental"),
            "is_rest": data.get("is_rest", 0),
            "rest_type": data.get("rest_type"),
            "rest_amount": data.get("rest_amount", 0)
        }

    def _add_activity_from_data(self, data, **kwargs):
        add_activity(**self._activity_kwargs_from_data(data, **kwargs))

    def _update_activity_from_data(self, activity_id, data, *, date, recurring=0, recurring_days=None, recurring_date=None):
        update_activity(
            activity_id, data["name"], data["category"],
            data["sh"], data["sm"], data["eh"], data["em"],
            data["difficulty"],
            date=date,
            recurring=recurring,
            recurring_days=recurring_days,
            recurring_date=recurring_date,
            load_type=data.get("load_type", "mental"),
            is_rest=data.get("is_rest", 0),
            rest_type=data.get("rest_type"),
            rest_amount=data.get("rest_amount", 0)
        )

    def _find_similar_one_time_activities(self, activity):
        all_activities = get_all_activities()
        return [
            act for act in all_activities
            if (
                act[1] == activity[1] and
                act[2] == activity[2] and
                act[3] == activity[3] and act[4] == activity[4] and
                act[5] == activity[5] and act[6] == activity[6] and
                act[9] == 0
            )
        ]

    def _select_days_for_similar(self, activity, title, text):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        btn_one = msg.addButton("Jen tuto", QMessageBox.AcceptRole)
        btn_selected = msg.addButton("Vybrané dny", QMessageBox.AcceptRole)
        btn_cancel = msg.addButton("Zrušit", QMessageBox.RejectRole)
        msg.exec()

        if msg.clickedButton() == btn_cancel:
            return None
        if msg.clickedButton() == btn_one:
            return []

        pseudo_activity = list(activity)
        pseudo_activity[9] = 1
        pseudo_activity = tuple(pseudo_activity)

        select_dlg = SelectDaysDialog(self, pseudo_activity, self.date, filter_by_activity=False)
        if not select_dlg.exec():
            return None
        dates = select_dlg.get_dates()
        if not dates:
            QMessageBox.warning(self, "Žádné dny", "Nebyly vybrány žádné dny.")
            return None
        return dates

    def _apply_replace_conflicts(self, conflicts, date_str, *, replace_mode):
        for conflict in conflicts:
            if replace_mode == "delete_all":
                delete_activity(conflict[0])
                continue
            if conflict[9] == 0:
                delete_activity(conflict[0])
            else:
                add_activity_exception(conflict[0], date_str)

    def _resolve_conflicts(self, data, existing_activities, date_str, *, replace_mode):
        conflicts = check_conflicts(data, existing_activities, date_str)
        if not conflicts:
            return data

        cr = ConflictResolutionDialog(self, data, conflicts)
        cr.exec()
        choice = cr.choice
        if choice in ("cancel", None):
            return None

        if choice == "replace":
            self._apply_replace_conflicts(conflicts, date_str, replace_mode=replace_mode)
            return data

        if choice == "shift_new":
            last_end = max(c[5] * 60 + c[6] for c in conflicts)
            new_slot = find_first_free_slot(data, existing_activities, date_str, last_end)
            if not new_slot:
                QMessageBox.information(self, "Aktivita se nevejde", "V tento den se není volný čas pro danou aktivitu. Aktivita nebude přidána.")
                return None
            return {**data, **new_slot}

        if choice == "shift_existing":
            if any(c[9] == 1 for c in conflicts):
                QMessageBox.information(self, "Nelze posunout", "Nelze posunout dlouhodobé aktivity. Aktivita nebude přidána.")
                return None
            new_end = data["eh"] * 60 + data["em"]
            for c in sorted(conflicts, key=lambda x: (x[3], x[4])):
                dur = (c[5] * 60 + c[6]) - (c[3] * 60 + c[4])
                new_start = new_end
                new_end = new_start + dur
                if new_end > 1439:
                    QMessageBox.information(self, "Nelze posunout", "Posun by překročil konec dne. Aktivita nebude přidána.")
                    return None
                update_activity(
                    c[0], c[1], c[2],
                    new_start // 60, new_start % 60,
                    new_end // 60, new_end % 60,
                    c[7], date=c[8],
                    recurring=c[9],
                    recurring_days=c[10],
                    recurring_date=c[11],
                    load_type=c[12] if len(c) > 12 and c[12] else "mental"
                )
            return data

        return data

    def calendar_dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def edit_selected(self):
        if not self.selected_activity:
            QMessageBox.warning(self, "Upozornění", "Vyber aktivitu k úpravě!")
            return

        activity = self.selected_activity

        if activity[9] == 1:  # recurring
            msg = QMessageBox(self)
            msg.setWindowTitle("Upravit dlouhodobou aktivitu")
            msg.setText("Chcete upravit jen tento den, celou sérii, nebo vybrané dny?")
            btn_one = msg.addButton("Jen tento den", QMessageBox.AcceptRole)
            btn_selected = msg.addButton("Vybrané dny", QMessageBox.AcceptRole)
            btn_series = msg.addButton("Celou sérii", QMessageBox.AcceptRole)
            btn_cancel = msg.addButton("Zrušit", QMessageBox.RejectRole)
            msg.setMinimumWidth(400)
            msg.exec()

            if msg.clickedButton() == btn_cancel:
                return

            if msg.clickedButton() == btn_one:
                dlg = EditActivityDialog(self, activity[0], is_recurring_instance=True)
                if dlg.exec():
                    data = dlg.get_data()
                    add_activity_exception(activity[0], data["date"])
                    self._add_activity_from_data(data, date=data["date"])
                    self.selected_activity = None
                    self.selected_widget = None
                    self.refresh()
                return

            if msg.clickedButton() == btn_selected:
                # Vyber dny
                select_dlg = SelectDaysDialog(self, activity, self.date)
                if not select_dlg.exec():
                    return
                dates = select_dlg.get_dates()
                if not dates:
                    QMessageBox.warning(self, "Žádné dny", "Nebyly vybrány žádné dny.")
                    return

                # Upravit pro vybrané dny
                dlg = EditActivityDialog(self, activity[0], is_recurring_instance=True)
                if dlg.exec():
                    data = dlg.get_data()
                    for date_str in dates:
                        add_activity_exception(activity[0], date_str)
                        self._add_activity_from_data(data, date=date_str)
                    self.selected_activity = None
                    self.selected_widget = None
                    self.refresh()
                return

            if msg.clickedButton() == btn_series:
                dlg = EditActivityDialog(self, activity[0], is_recurring_instance=False)
                if dlg.exec():
                    data = dlg.get_data()
                    self._update_activity_from_data(
                        activity[0],
                        data,
                        date=None,
                        recurring=1,
                        recurring_days=activity[10],
                        recurring_date=activity[11]
                    )
                    self.selected_activity = None
                    self.selected_widget = None
                    self.refresh()
                return

        # Jednorázová aktivita - zkontroluj, zda existují další stejné
        else:
            # Najdi všechny aktivity se stejným názvem, časem a kategorií
            similar_activities = self._find_similar_one_time_activities(activity)

            # Pokud existuje více než jedna taková aktivita, nabídni možnosti
            if len(similar_activities) > 1:
                dates = self._select_days_for_similar(
                    activity,
                    "Upravit aktivitu",
                    f"Nalezeno {len(similar_activities)} podobných aktivit.\nChcete upravit jen tuto, nebo vybrané dny?"
                )
                if dates is None:
                    return
                if dates:
                    dlg = EditActivityDialog(self, activity[0], is_recurring_instance=True)
                    if dlg.exec():
                        data = dlg.get_data()
                        for act in similar_activities:
                            if act[8] in dates:
                                self._update_activity_from_data(act[0], data, date=act[8])
                        self.selected_activity = None
                        self.selected_widget = None
                        self.refresh()
                    return

        # Jednorázová aktivita - standardní úprava
        dlg = EditActivityDialog(self, activity[0], is_recurring_instance=False)
        if dlg.exec():
            data = dlg.get_data()
            self._update_activity_from_data(activity[0], data, date=data["date"])
            self.selected_activity = None
            self.selected_widget = None
            self.refresh()

    def delete_selected(self):
        if not self.selected_activity:
            QMessageBox.warning(self, "Upozornění", "Vyber aktivitu ke smazání!")
            return

        activity = self.selected_activity

        if activity[9] == 1:  # recurring
            msg = QMessageBox(self)
            msg.setWindowTitle("Smazat dlouhodobou aktivitu")
            msg.setText("Chcete smazat jen tento den, vybrané dny, nebo celou sérii?")
            btn_one = msg.addButton("Jen tento den", QMessageBox.AcceptRole)
            btn_selected = msg.addButton("Vybrané dny", QMessageBox.AcceptRole)
            btn_series = msg.addButton("Celou sérii", QMessageBox.DestructiveRole)
            btn_cancel = msg.addButton("Zrušit", QMessageBox.RejectRole)
            msg.exec()

            if msg.clickedButton() == btn_cancel:
                return

            if msg.clickedButton() == btn_one:
                # Vytvoř výjimku pro tento den
                add_activity_exception(activity[0], self.date)
                self.selected_activity = None
                self.selected_widget = None
                self.refresh()
                return

            if msg.clickedButton() == btn_selected:
                # Vyber dny
                select_dlg = SelectDaysDialog(self, activity, self.date)
                if not select_dlg.exec():
                    return
                dates = select_dlg.get_dates()
                if not dates:
                    QMessageBox.warning(self, "Žádné dny", "Nebyly vybrány žádné dny.")
                    return

                # Smaž pro vybrané dny
                reply = QMessageBox.question(self, "Potvrzení",
                    f"Opravdu smazat aktivitu '{activity[1]}' v {len(dates)} dnech?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    for date_str in dates:
                        add_activity_exception(activity[0], date_str)
                    self.selected_activity = None
                    self.selected_widget = None
                    self.refresh()
                return

            if msg.clickedButton() == btn_series:
                reply = QMessageBox.question(self, "Potvrzení",
                    f"Opravdu smazat CELOU SÉRII '{activity[1]}'?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    delete_activity(activity[0])
                    self.selected_activity = None
                    self.selected_widget = None
                    self.refresh()
                return

        # Jednorázová aktivita - zkontroluj, zda existují další stejné
        else:
            # Najdi všechny aktivity se stejným názvem, časem a kategorií
            similar_activities = self._find_similar_one_time_activities(activity)

            # Pokud existuje více než jedna taková aktivita, nabídni možnosti
            if len(similar_activities) > 1:
                dates = self._select_days_for_similar(
                    activity,
                    "Smazat aktivitu",
                    f"Nalezeno {len(similar_activities)} podobných aktivit.\nChcete smazat jen tuto, nebo vybrané dny?"
                )
                if dates is None:
                    return
                if dates:
                    reply = QMessageBox.question(
                        self,
                        "Potvrzení",
                        f"Opravdu smazat aktivitu '{activity[1]}' v {len(dates)} dnech?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        for act in similar_activities:
                            if act[8] in dates:
                                delete_activity(act[0])
                        self.selected_activity = None
                        self.selected_widget = None
                        self.refresh()
                    return

        # Jednorázová aktivita - standardní smazání
        reply = QMessageBox.question(self, "Potvrzení",
            f"Opravdu smazat aktivitu '{activity[1]}'?",
            QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            delete_activity(activity[0])
            self.selected_activity = None
            self.selected_widget = None
            self.refresh()

    def sort_activities(self, activities):
        all_day = []
        timed = []

        for act in activities:
            if is_all_day_activity(act):
                all_day.append(act)
            else:
                timed.append(act)

        timed.sort(key=lambda x: (x[3], x[4]))

        return all_day + timed

    def refresh(self):
        while self.activity_layout.count():
            child = self.activity_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.selected_activity = None
        self.selected_widget = None

        activities = get_activities_for_day(self.date)
        sorted_activities = self.sort_activities(activities)

        if not sorted_activities:
            empty_label = QLabel("Žádné aktivity pro tento den")
            empty_label.setStyleSheet("color: #999; font-size: 12px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.activity_layout.addWidget(empty_label)
        else:
            for act in sorted_activities:
                widget = ActivityWidget(act, current_date=self.date)
                widget.clicked.connect(self.on_activity_clicked)
                widget.request_edit.connect(self.on_request_edit)
                widget.request_delete.connect(self.on_request_delete)
                widget.request_add_note.connect(self.on_request_add_note)
                self.activity_layout.addWidget(widget)

        self.activity_layout.addStretch()
        self.update_recommendation()

    def on_activity_clicked(self, activity, widget):
        if self.selected_widget:
            self.selected_widget.set_selected(False)
        self.selected_activity = activity
        self.selected_widget = widget
        widget.set_selected(True)

    def on_request_edit(self, activity):
        self.selected_activity = activity
        self.edit_selected()

    def on_request_delete(self, activity):
        self.selected_activity = activity
        self.delete_selected()

    def on_request_add_note(self, activity, date):
        dlg = AddNoteDialog(self, activity, date)
        if dlg.exec():
            note_text = dlg.get_note()
            if dlg.deleted or not note_text:
                delete_activity_note(activity[0], date)
            else:
                add_or_update_activity_note(activity[0], date, note_text)
            self.refresh()

    def on_date_changed(self):
        self.date = self.calendar.selectedDate().toString("yyyy-MM-dd")
        self.refresh()
