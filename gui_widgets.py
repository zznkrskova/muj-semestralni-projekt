from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QFont, QDrag

from database import get_activity_note
from logic import format_activity_time


class ActivityWidget(QWidget):
    """Custom widget pro zobrazení aktivity s barvou podle náročnosti"""
    DIFFICULTY_COLORS = {
        1: "#5FA5FF",
        2: "#3D8CFF",
        3: "#1E6FFF",
        4: "#0F53CC",
        5: "#083A99"
    }
    clicked = Signal(object, object)
    request_edit = Signal(object)
    request_delete = Signal(object)
    request_add_note = Signal(object, object)  # activity, current_date

    def __init__(self, activity, parent=None, current_date=None):
        super().__init__(parent)
        self.activity = activity
        self.current_date = current_date
        self.setObjectName("activityBubble")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAcceptDrops(False)
        self.drag_start_position = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        difficulty = self.activity[7]
        color = self.get_color_by_difficulty(difficulty)

        self.base_style = f"""
            #activityBubble {{
                background-color: {color};
                border-radius: 10px;
                border: none;
            }}
            #activityBubble QLabel {{
                background-color: transparent;
                border: none;
            }}
        """
        self.setStyleSheet(self.base_style)

        # Název
        name_label = QLabel(self.activity[1])
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: white;")
        layout.addWidget(name_label)

        # Čas
        time_str = format_activity_time(self.activity)
        time_label = QLabel(time_str)
        time_font = QFont()
        time_font.setPointSize(9)
        time_label.setFont(time_font)
        time_label.setStyleSheet("color: rgba(255, 255, 255, 0.95);")
        layout.addWidget(time_label)

        # Kategorie
        category_label = QLabel(self.activity[2])
        cat_font = QFont()
        cat_font.setPointSize(8)
        cat_font.setItalic(True)
        category_label.setFont(cat_font)
        category_label.setStyleSheet("color: rgba(255, 255, 255, 0.85);")
        layout.addWidget(category_label)

        # Poznámka (pokud existuje)
        if self.current_date:
            note = get_activity_note(self.activity[0], self.current_date)
            if note:
                note_label = QLabel(f"📝 {note}")
                note_font = QFont()
                note_font.setPointSize(8)
                note_label.setFont(note_font)
                note_label.setStyleSheet("color: rgba(255, 255, 200, 0.9);")
                note_label.setWordWrap(True)
                layout.addWidget(note_label)

        self.setMinimumHeight(90)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
            self.clicked.emit(self.activity, self)
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if self.drag_start_position is None:
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < 20:
            return

        # Allow drag for both recurring and non-recurring
        drag = QDrag(self)
        mime_data = QMimeData()
        # Store activity ID, recurring status, and origin date
        origin_date = self.current_date or ""
        mime_data.setText(f"{self.activity[0]}|{self.activity[9]}|{origin_date}")
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = menu.addAction("Upravit")
        note_action = menu.addAction("Přidat/upravit poznámku")
        delete_action = menu.addAction("Smazat")

        action = menu.exec_(self.mapToGlobal(pos))
        if action == edit_action:
            self.request_edit.emit(self.activity)
        elif action == note_action:
            self.request_add_note.emit(self.activity, self.current_date)
        elif action == delete_action:
            self.request_delete.emit(self.activity)

    def set_selected(self, selected: bool):
        if selected:
            self.setStyleSheet(self.base_style + "\n#activityBubble { border: 3px solid #FFD166; }")
        else:
            self.setStyleSheet(self.base_style)

    def get_color_by_difficulty(self, difficulty):
        return self.DIFFICULTY_COLORS.get(difficulty, "#3D8CFF")
