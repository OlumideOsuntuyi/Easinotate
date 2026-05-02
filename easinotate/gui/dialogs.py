"""Dialogs used by Easinotate GUI."""
from __future__ import annotations
import os
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QFileDialog, QComboBox, QCheckBox, QMessageBox,
    QListWidget, QListWidgetItem, QColorDialog, QWidget, QDialogButtonBox,
    QGroupBox, QSpinBox
)


class NewDatasetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Dataset")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Create a new annotation dataset")
        title.setProperty("heading", True)
        layout.addWidget(title)

        sub = QLabel("Choose a name and a folder where the dataset will be stored.")
        sub.setProperty("muted", True)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. household_appliances_v1")
        form.addRow("Name *", self.name_input)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Optional description...")
        self.desc_input.setMaximumHeight(80)
        form.addRow("Description", self.desc_input)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Pick a folder...")
        self.path_input.setReadOnly(True)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_input)
        path_row.addWidget(browse)
        form.addRow("Location *", path_row)
        layout.addLayout(form)

        layout.addStretch()
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Create")
        ok.setProperty("primary", True)
        ok.setDefault(True)
        ok.clicked.connect(self._on_ok)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        layout.addLayout(btns)

        self._result_path = ""
        self._result_name = ""
        self._result_desc = ""

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select parent folder for dataset")
        if d:
            self.path_input.setText(d)

    def _on_ok(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a dataset name.")
            return
        if not all(c.isalnum() or c in "_- " for c in name):
            QMessageBox.warning(self, "Invalid name",
                "Name must contain only letters, numbers, spaces, dashes, or underscores.")
            return
        parent = self.path_input.text().strip()
        if not parent:
            QMessageBox.warning(self, "Missing location", "Please choose a parent folder.")
            return
        if not os.path.isdir(parent):
            QMessageBox.warning(self, "Invalid location", "The chosen folder does not exist.")
            return

        safe_name = name.replace(" ", "_")
        full = os.path.join(parent, safe_name)
        if os.path.exists(full):
            ans = QMessageBox.question(
                self, "Folder exists",
                f"The folder '{safe_name}' already exists in this location.\n\n"
                "Continue and overwrite/merge into it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        self._result_name = name
        self._result_desc = self.desc_input.toPlainText().strip()
        self._result_path = full
        self.accept()

    def get_result(self):
        return self._result_name, self._result_desc, self._result_path


class URLImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Image from URL")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Import image from URL")
        title.setProperty("heading", True)
        layout.addWidget(title)
        sub = QLabel("Paste a direct image URL (jpg, png, gif, webp, etc.).")
        sub.setProperty("muted", True)
        layout.addWidget(sub)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/image.jpg")
        layout.addWidget(self.url_input)

        layout.addStretch()
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        ok = QPushButton("Import"); ok.setProperty("primary", True); ok.setDefault(True)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel); btns.addWidget(ok)
        layout.addLayout(btns)

    def get_url(self) -> str:
        return self.url_input.text().strip()


class LabelEditorDialog(QDialog):
    """Manage labels and their colors for the dataset."""
    def __init__(self, dataset, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.setWindowTitle("Manage Labels")
        self.setMinimumWidth(440)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Manage labels")
        title.setProperty("heading", True)
        layout.addWidget(title)
        sub = QLabel("Add labels and pick a color for each. Colors are reused for new bounding boxes.")
        sub.setWordWrap(True)
        sub.setProperty("muted", True)
        layout.addWidget(sub)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        add_row = QHBoxLayout()
        self.new_label_input = QLineEdit()
        self.new_label_input.setPlaceholderText("New label name (e.g. ceiling fan)")
        add_btn = QPushButton("Add")
        add_btn.setProperty("primary", True)
        add_btn.clicked.connect(self._add_label)
        add_row.addWidget(self.new_label_input)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        action_row = QHBoxLayout()
        color_btn = QPushButton("Change Color...")
        color_btn.clicked.connect(self._change_color)
        del_btn = QPushButton("Remove")
        del_btn.setProperty("danger", True)
        del_btn.clicked.connect(self._remove_selected)
        action_row.addWidget(color_btn)
        action_row.addWidget(del_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        close = QPushButton("Done")
        close.clicked.connect(self.accept)
        bot = QHBoxLayout(); bot.addStretch(); bot.addWidget(close)
        layout.addLayout(bot)

        self._refresh()

    def _refresh(self):
        self.list_widget.clear()
        labels = sorted(set(self.dataset.label_set) | set(self.dataset.label_colors.keys()))
        for lbl in labels:
            color = self.dataset.get_label_color(lbl)
            item = QListWidgetItem(f"   {lbl}")
            item.setData(Qt.ItemDataRole.UserRole, lbl)
            from PyQt6.QtGui import QPixmap
            pm = QPixmap(16, 16); pm.fill(QColor(color))
            item.setIcon(self._make_icon(color))
            self.list_widget.addItem(item)

    def _make_icon(self, color_hex):
        from PyQt6.QtGui import QPixmap, QPainter
        pm = QPixmap(18, 18)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color_hex))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(2, 2, 14, 14, 3, 3)
        p.end()
        from PyQt6.QtGui import QIcon
        return QIcon(pm)

    def _add_label(self):
        name = self.new_label_input.text().strip()
        if not name:
            return
        if name not in self.dataset.label_colors:
            # Generate a color from a palette
            self.dataset.set_label_color(name, _next_palette_color(self.dataset))
        self.new_label_input.clear()
        self._refresh()

    def _change_color(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        lbl = item.data(Qt.ItemDataRole.UserRole)
        cur = QColor(self.dataset.get_label_color(lbl))
        c = QColorDialog.getColor(cur, self, "Pick label color")
        if c.isValid():
            self.dataset.set_label_color(lbl, c.name())
            self._refresh()

    def _remove_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        lbl = item.data(Qt.ItemDataRole.UserRole)
        ans = QMessageBox.question(
            self, "Remove label",
            f"Remove label '{lbl}'?\n\nExisting annotations using this label will keep their text but lose color mapping.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.dataset.label_colors.pop(lbl, None)
            self.dataset.touch()
            self._refresh()


_PALETTE = [
    "#f38ba8", "#fab387", "#f9e2af", "#a6e3a1", "#74c7ec",
    "#89b4fa", "#cba6f7", "#f5c2e7", "#94e2d5", "#eba0ac",
]


def _next_palette_color(dataset) -> str:
    used = set(dataset.label_colors.values())
    for c in _PALETTE:
        if c not in used:
            return c
    # fallback: rotate
    return _PALETTE[len(dataset.label_colors) % len(_PALETTE)]


class ExportDialog(QDialog):
    """Dialog to choose export format and destination."""
    FORMATS = [
        ("Folder structure (recommended)", "folder",
         "Categorize images into folders by their primary label, with sidecar JSON files."),
        ("COCO JSON", "coco",
         "Standard COCO format used by most object detection toolkits."),
        ("YOLO darknet", "yolo",
         "Per-image .txt files plus classes.txt and data.yaml."),
        ("Pascal VOC", "voc",
         "Per-image .xml annotations in Pascal VOC layout."),
    ]

    def __init__(self, dataset, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.setWindowTitle("Export Dataset")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Export annotation dataset")
        title.setProperty("heading", True)
        layout.addWidget(title)

        info = QLabel(
            f"<b>Dataset:</b> {dataset.name}<br>"
            f"<b>Images:</b> {len(dataset.images)} &nbsp;&nbsp; "
            f"<b>Boxes:</b> {dataset.total_bboxes} &nbsp;&nbsp; "
            f"<b>Labels:</b> {len(dataset.label_set)}"
        )
        info.setProperty("muted", True)
        layout.addWidget(info)

        fmt_group = QGroupBox("Format")
        fg = QVBoxLayout(fmt_group)
        self.fmt_combo = QComboBox()
        for label, _, _ in self.FORMATS:
            self.fmt_combo.addItem(label)
        self.fmt_desc = QLabel(self.FORMATS[0][2])
        self.fmt_desc.setWordWrap(True)
        self.fmt_desc.setProperty("muted", True)
        self.fmt_combo.currentIndexChanged.connect(
            lambda i: self.fmt_desc.setText(self.FORMATS[i][2])
        )
        fg.addWidget(self.fmt_combo)
        fg.addWidget(self.fmt_desc)
        layout.addWidget(fmt_group)

        opts = QGroupBox("Options")
        og = QVBoxLayout(opts)
        self.include_unlabeled = QCheckBox("Include unlabeled images in export")
        self.include_unlabeled.setChecked(True)
        og.addWidget(self.include_unlabeled)
        layout.addWidget(opts)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Choose where to save the .zip file")
        self.path_input.setReadOnly(True)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_input)
        path_row.addWidget(browse)
        layout.addLayout(path_row)

        layout.addStretch()
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        ok = QPushButton("Export"); ok.setProperty("primary", True); ok.setDefault(True)
        ok.clicked.connect(self._on_ok)
        btns.addWidget(cancel); btns.addWidget(ok)
        layout.addLayout(btns)

    def _browse(self):
        suggested = f"{self.dataset.name}_export.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save export as...", suggested, "ZIP archive (*.zip)"
        )
        if path:
            if not path.lower().endswith(".zip"):
                path += ".zip"
            self.path_input.setText(path)

    def _on_ok(self):
        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Missing path", "Please choose where to save the export.")
            return
        self.accept()

    def get_options(self):
        idx = self.fmt_combo.currentIndex()
        fmt_key = self.FORMATS[idx][1]
        return {
            "format": fmt_key,
            "path": self.path_input.text().strip(),
            "include_unlabeled": self.include_unlabeled.isChecked(),
        }


class AboutDialog(QDialog):
    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Easinotate")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        title = QLabel("Easinotate")
        title.setProperty("heading", True)
        layout.addWidget(title)

        ver = QLabel(f"Version {version}")
        ver.setProperty("muted", True)
        layout.addWidget(ver)

        body = QLabel(
            "A modern, lightweight image annotation framework.\n\n"
            "• Draw and edit bounding boxes\n"
            "• Per-box and per-image labels\n"
            "• Folder-based categorization on export\n"
            "• Multi-format export (Folder, COCO, YOLO, Pascal VOC)\n"
            "• Import from filesystem or URL\n"
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        ok = QPushButton("Close")
        ok.setProperty("primary", True)
        ok.clicked.connect(self.accept)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(ok)
        layout.addLayout(row)
