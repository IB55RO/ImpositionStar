import sys
from PySide6 import QtCore, QtGui, QtWidgets


VIOLET_BG = "#D9C3F0"
ACCENT = "#6B4BB4"
ACCENT_DARK = "#5A3EA0"
TEXT_MAIN = "#1F2937"
CARD_BG = "#FFFFFF"


def _apply_app_font(app: QtWidgets.QApplication) -> None:
    font = QtGui.QFont("Montserrat", 11)
    font.setWeight(QtGui.QFont.Weight.DemiBold)
    app.setFont(font)


class RoundedWindow(QtWidgets.QWidget):
    def __init__(self, radius: int = 16, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.Window
        )

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(rect), self._radius, self._radius)
        painter.fillPath(path, QtGui.QBrush(QtGui.QColor(VIOLET_BG)))
        pen = QtGui.QPen(QtGui.QColor("#B59EDB"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)
        super().paintEvent(event)


class TitleBar(QtWidgets.QWidget):
    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_pos: QtCore.QPoint | None = None
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet("color: #1F2937; font-size: 14px; font-weight: 600;")
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.close_button = QtWidgets.QPushButton("✕")
        self.close_button.setFixedSize(28, 28)
        self.close_button.setStyleSheet(
            "QPushButton { background: #EEE6FF; border-radius: 8px; }"
            "QPushButton:hover { background: #E2D6FF; }"
        )
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_pos is None:
            return
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.window().move(self.window().pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_pos = None


class MainWindow(RoundedWindow):
    def __init__(self) -> None:
        super().__init__(radius=18)
        self.setObjectName("MainWindow")
        self.setMinimumSize(880, 720)

        container = QtWidgets.QVBoxLayout(self)
        container.setContentsMargins(0, 0, 0, 0)

        title_bar = TitleBar("Imposition Star – PySide6 UI")
        title_bar.close_button.clicked.connect(self.close)
        container.addWidget(title_bar)

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(32, 16, 32, 24)
        body_layout.setSpacing(18)
        container.addWidget(body)

        self._build_form(body_layout)
        self._build_actions(body_layout)

        self._apply_styles()

    def _build_form(self, layout: QtWidgets.QVBoxLayout) -> None:
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_button = QtWidgets.QPushButton("Alege...")
        folder_row = QtWidgets.QHBoxLayout()
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(self.folder_button)
        folder_widget = QtWidgets.QWidget()
        folder_widget.setLayout(folder_row)
        form.addRow("Folder cu PDF-uri (#N):", folder_widget)

        self.sheet_combo = QtWidgets.QComboBox()
        self.sheet_combo.addItems([
            "70x50 cm", "100x70 cm", "64x45 cm", "64x44 cm", "50x35 cm",
            "48.7x32 cm", "A2 (594x420 mm)", "A1 (841x594 mm)", "A4 29.7x21 cm", "Custom (cm)"
        ])
        sheet_row = QtWidgets.QHBoxLayout()
        sheet_row.addWidget(self.sheet_combo)
        self.sheet_w = QtWidgets.QLineEdit()
        self.sheet_w.setFixedWidth(90)
        self.sheet_h = QtWidgets.QLineEdit()
        self.sheet_h.setFixedWidth(90)
        sheet_row.addWidget(QtWidgets.QLabel("Lățime (cm):"))
        sheet_row.addWidget(self.sheet_w)
        sheet_row.addWidget(QtWidgets.QLabel("Înălțime (cm):"))
        sheet_row.addWidget(self.sheet_h)
        sheet_row.addStretch()
        sheet_widget = QtWidgets.QWidget()
        sheet_widget.setLayout(sheet_row)
        form.addRow("Format coală:", sheet_widget)

        self.gap_edit = QtWidgets.QLineEdit("3.0")
        self.cropbox_combo = QtWidgets.QComboBox()
        self.cropbox_combo.addItems(["0", "1", "1.5", "2", "3"])
        self.margin_edit = QtWidgets.QLineEdit("5.0")
        self.bottom_margin_edit = QtWidgets.QLineEdit("12.0")
        self.bleed_edit = QtWidgets.QLineEdit("3.0")
        self.crop_len_edit = QtWidgets.QLineEdit("3.0")
        self.crop_width_edit = QtWidgets.QLineEdit("0.3")
        self.scale_edit = QtWidgets.QLineEdit("100")

        form.addRow("Gap (mm):", self.gap_edit)
        form.addRow("Cropbox (mm):", self.cropbox_combo)
        form.addRow("Margine (mm):", self.margin_edit)
        form.addRow("Marginea de jos (mm):", self.bottom_margin_edit)
        form.addRow("Bleed (mm):", self.bleed_edit)
        form.addRow("Lungime crop (mm):", self.crop_len_edit)
        form.addRow("Grosime linie crop (mm):", self.crop_width_edit)
        form.addRow("Scalare piese (%):", self.scale_edit)

        self.rotate_check = QtWidgets.QCheckBox("Permite rotire")
        layout.addLayout(form)
        layout.addWidget(self.rotate_check)

        mode_group = QtWidgets.QGroupBox("Mod impoziție")
        mode_layout = QtWidgets.QVBoxLayout(mode_group)
        self.mode_front_back = QtWidgets.QRadioButton("Față pe pagina 1, Verso pe pagina 2")
        self.mode_paired = QtWidgets.QRadioButton("Față + Verso în aceeași pagină")
        self.mode_fronts_only = QtWidgets.QRadioButton("Doar Față")
        self.mode_front_back.setChecked(True)
        mode_layout.addWidget(self.mode_front_back)
        mode_layout.addWidget(self.mode_paired)
        mode_layout.addWidget(self.mode_fronts_only)
        layout.addWidget(mode_group)

        explore_group = QtWidgets.QGroupBox("Explorare (enumerare compat)")
        explore_form = QtWidgets.QFormLayout(explore_group)
        self.num_variants = QtWidgets.QLineEdit("100")
        self.limit_combos = QtWidgets.QLineEdit("1200")
        self.preview_scale = QtWidgets.QLineEdit("23")
        self.seed = QtWidgets.QLineEdit("2025")
        explore_form.addRow("Număr variante (2–100):", self.num_variants)
        explore_form.addRow("Limită combinații testate:", self.limit_combos)
        explore_form.addRow("Scară preview (%):", self.preview_scale)
        explore_form.addRow("Seed (random):", self.seed)
        layout.addWidget(explore_group)

    def _build_actions(self, layout: QtWidgets.QVBoxLayout) -> None:
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        self.preview_button = QtWidgets.QPushButton("Generează VARIANTE (preview)")
        self.final_button = QtWidgets.QPushButton("Generează PDF final")
        actions.addWidget(self.preview_button)
        actions.addWidget(self.final_button)
        layout.addLayout(actions)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#MainWindow {{
                background: {VIOLET_BG};
                color: {TEXT_MAIN};
                border-radius: 18px;
            }}
            QLabel {{
                font-size: 16px;
                font-weight: 600;
            }}
            QLineEdit, QComboBox {{
                background: {CARD_BG};
                border: 1px solid #B9A7DD;
                border-radius: 12px;
                padding: 6px 10px;
                font-size: 16px;
                font-weight: 600;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QGroupBox {{
                border: 1px solid #B9A7DD;
                border-radius: 14px;
                margin-top: 12px;
                padding: 12px;
                font-size: 16px;
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
            }}
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7C5CD6,
                    stop:1 {ACCENT}
                );
                color: white;
                border: 1px solid #51318F;
                border-radius: 14px;
                padding: 10px 18px;
                font-size: 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #8C6BE0,
                    stop:1 {ACCENT_DARK}
                );
            }}
            QPushButton:pressed {{
                background: {ACCENT_DARK};
            }}
            QCheckBox, QRadioButton {{
                font-size: 16px;
                font-weight: 600;
            }}
            """
        )


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    _apply_app_font(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
