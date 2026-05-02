"""Main window for Easinotate."""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QAction, QPixmap, QIcon, QKeySequence, QColor, QPainter, QFont
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QLabel, QToolBar, QPushButton, QFileDialog, QMessageBox,
    QStatusBar, QLineEdit, QComboBox, QGroupBox, QFormLayout, QTextEdit,
    QInputDialog, QFrame, QSizePolicy, QStyle, QApplication, QProgressDialog,
    QTreeWidget, QTreeWidgetItem
)

from ..core.dataset import Dataset
from ..core.annotation import BoundingBox, ImageAnnotation
from ..core.exporter import Exporter
from ..utils.image_loader import (
    import_from_path, import_from_url, ImageLoadError, VALID_EXT,
    scan_folder, derive_primary_label,
)
from .canvas import AnnotationCanvas, BBoxItem
from .dialogs import (
    NewDatasetDialog, URLImportDialog, LabelEditorDialog,
    ExportDialog, AboutDialog, _next_palette_color
)
from .duplicates_dialog import DuplicatesDialog


APP_VERSION = "1.0.0"
AUTOSAVE_INTERVAL_MS = 30_000  # 30s


def _make_color_icon(color_hex: str, size: int = 14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color_hex))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Easinotate")
        self.resize(1400, 880)

        self.dataset: Optional[Dataset] = None
        self.current_image: Optional[ImageAnnotation] = None
        self._dirty = False

        # Image-list filter / grouping state
        self._filter_text: str = ""
        self._filter_mode: str = "all"   # all | annotated | unannotated | has_primary | no_primary | from_url
        self._group_mode: str = "none"   # none | primary
        self._visible_count: int = 0

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._update_ui_state()

        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(AUTOSAVE_INTERVAL_MS)

    # ---------- UI construction ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        # ----- left: dataset & images list -----
        left = QWidget()
        ll = QVBoxLayout(left); ll.setContentsMargins(12, 12, 12, 12); ll.setSpacing(10)

        self.dataset_header = QLabel("No dataset loaded")
        self.dataset_header.setProperty("heading", True)
        ll.addWidget(self.dataset_header)
        self.dataset_subtitle = QLabel("Create or open a dataset to begin")
        self.dataset_subtitle.setProperty("muted", True)
        self.dataset_subtitle.setWordWrap(True)
        ll.addWidget(self.dataset_subtitle)

        ll.addWidget(self._hr())

        images_label = QLabel("Images")
        images_label.setProperty("subheading", True)
        ll.addWidget(images_label)

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename or label...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        ll.addWidget(self.search_input)

        # Filter + group combos on one row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.filter_combo = QComboBox()
        for label, key in [
            ("All",                "all"),
            ("Annotated",          "annotated"),
            ("Unannotated",        "unannotated"),
            ("Has primary label",  "has_primary"),
            ("No primary label",   "no_primary"),
            ("From URL",           "from_url"),
        ]:
            self.filter_combo.addItem(label, key)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.filter_combo, 1)

        self.group_combo = QComboBox()
        self.group_combo.addItem("Flat list", "none")
        self.group_combo.addItem("Group by primary label", "primary")
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        filter_row.addWidget(self.group_combo, 1)
        ll.addLayout(filter_row)

        # Compact list — small icon, single-line rows.
        self.images_list = QListWidget()
        self.images_list.setIconSize(QSize(28, 28))
        self.images_list.setUniformItemSizes(False)  # group headers can be taller
        self.images_list.setSpacing(0)
        self.images_list.setStyleSheet(
            "QListWidget::item { padding: 4px 6px; }"
        )
        self.images_list.currentItemChanged.connect(self._on_image_selected)
        ll.addWidget(self.images_list, 1)

        # Visible-count footer
        self.images_count_label = QLabel("")
        self.images_count_label.setProperty("muted", True)
        ll.addWidget(self.images_count_label)

        btn_row = QHBoxLayout()
        self.btn_add_file = QPushButton("Add File")
        self.btn_add_file.clicked.connect(self.add_image_from_file)
        self.btn_add_url = QPushButton("From URL")
        self.btn_add_url.clicked.connect(self.add_image_from_url)
        self.btn_add_folder = QPushButton("Folder…")
        self.btn_add_folder.clicked.connect(self.add_images_from_folder)
        btn_row.addWidget(self.btn_add_file)
        btn_row.addWidget(self.btn_add_url)
        btn_row.addWidget(self.btn_add_folder)
        ll.addLayout(btn_row)

        self.btn_find_dups = QPushButton("Find duplicates…")
        self.btn_find_dups.clicked.connect(self.find_duplicates)
        ll.addWidget(self.btn_find_dups)

        self.btn_remove_image = QPushButton("Remove selected image")
        self.btn_remove_image.setProperty("danger", True)
        self.btn_remove_image.clicked.connect(self.remove_current_image)
        ll.addWidget(self.btn_remove_image)

        splitter.addWidget(left)

        # ----- center: canvas -----
        self.canvas = AnnotationCanvas()
        self.canvas.bbox_created.connect(self._on_bbox_created)
        self.canvas.bbox_changed.connect(self._on_bbox_changed)
        self.canvas.bbox_selected.connect(self._on_bbox_selected_in_canvas)
        self.canvas.bbox_deleted.connect(self._on_bbox_deleted)
        splitter.addWidget(self.canvas)

        # ----- right: annotation properties -----
        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(12, 12, 12, 12); rl.setSpacing(10)

        h2 = QLabel("Annotation")
        h2.setProperty("heading", True)
        rl.addWidget(h2)

        # active label group
        active_group = QGroupBox("Drawing label")
        ag = QVBoxLayout(active_group); ag.setSpacing(8)
        ag_help = QLabel("Boxes you draw next will use this label.")
        ag_help.setProperty("muted", True); ag_help.setWordWrap(True)
        ag.addWidget(ag_help)
        self.active_label_combo = QComboBox()
        self.active_label_combo.setEditable(True)
        self.active_label_combo.lineEdit().setPlaceholderText("Pick or type a label...")
        self.active_label_combo.currentTextChanged.connect(self._on_active_label_changed)
        ag.addWidget(self.active_label_combo)
        manage = QPushButton("Manage labels...")
        manage.clicked.connect(self.open_label_manager)
        ag.addWidget(manage)
        rl.addWidget(active_group)

        # bbox list group
        bbox_group = QGroupBox("Bounding boxes")
        bg = QVBoxLayout(bbox_group); bg.setSpacing(6)
        self.bbox_list = QListWidget()
        self.bbox_list.currentItemChanged.connect(self._on_bbox_list_selected)
        bg.addWidget(self.bbox_list)
        bbox_btns = QHBoxLayout()
        self.btn_relabel_box = QPushButton("Relabel")
        self.btn_relabel_box.clicked.connect(self._relabel_selected_bbox)
        self.btn_delete_box = QPushButton("Delete")
        self.btn_delete_box.setProperty("danger", True)
        self.btn_delete_box.clicked.connect(self._delete_selected_bbox)
        bbox_btns.addWidget(self.btn_relabel_box)
        bbox_btns.addWidget(self.btn_delete_box)
        bg.addLayout(bbox_btns)
        rl.addWidget(bbox_group, 1)

        # categorization group
        cat_group = QGroupBox("Image categorization")
        cl = QFormLayout(cat_group); cl.setSpacing(8)
        cat_help = QLabel(
            "Primary label decides the export folder. Use '/' for nested categories "
            "(e.g. <i>fans/ceiling fans</i>)."
        )
        cat_help.setWordWrap(True); cat_help.setProperty("muted", True)
        cl.addRow(cat_help)
        self.primary_label_input = QLineEdit()
        self.primary_label_input.setPlaceholderText("e.g. fans/ceiling fans")
        self.primary_label_input.editingFinished.connect(self._save_primary_label)
        cl.addRow("Primary label", self.primary_label_input)
        self.image_labels_input = QLineEdit()
        self.image_labels_input.setPlaceholderText("comma-separated, e.g. indoor, modern")
        self.image_labels_input.editingFinished.connect(self._save_image_labels)
        cl.addRow("Extra labels", self.image_labels_input)
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(70)
        self.notes_input.setPlaceholderText("Optional notes for this image...")
        self.notes_input.focusOutEvent = self._wrap_focus_out(self.notes_input.focusOutEvent, self._save_notes)
        cl.addRow("Notes", self.notes_input)
        rl.addWidget(cat_group)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([280, 800, 320])

    def _wrap_focus_out(self, original, then_call):
        def wrapper(event):
            original(event)
            then_call()
        return wrapper

    def _hr(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _build_menu(self):
        mb = self.menuBar()

        # File
        m_file = mb.addMenu("&File")
        a_new = QAction("New Dataset...", self); a_new.setShortcut(QKeySequence.StandardKey.New)
        a_new.triggered.connect(self.new_dataset)
        a_open = QAction("Open Dataset...", self); a_open.setShortcut(QKeySequence.StandardKey.Open)
        a_open.triggered.connect(self.open_dataset)
        a_save = QAction("Save", self); a_save.setShortcut(QKeySequence.StandardKey.Save)
        a_save.triggered.connect(self.save_dataset)
        a_export = QAction("Export...", self); a_export.setShortcut("Ctrl+E")
        a_export.triggered.connect(self.export_dataset)
        a_quit = QAction("Quit", self); a_quit.setShortcut(QKeySequence.StandardKey.Quit)
        a_quit.triggered.connect(self.close)
        m_file.addAction(a_new); m_file.addAction(a_open); m_file.addAction(a_save)
        m_file.addSeparator()
        m_file.addAction(a_export)
        m_file.addSeparator()
        m_file.addAction(a_quit)
        self.act_save = a_save
        self.act_export = a_export

        # Image
        m_img = mb.addMenu("&Image")
        a_add_file = QAction("Add image from file...", self); a_add_file.setShortcut("Ctrl+I")
        a_add_file.triggered.connect(self.add_image_from_file)
        a_add_url = QAction("Add image from URL...", self); a_add_url.setShortcut("Ctrl+U")
        a_add_url.triggered.connect(self.add_image_from_url)
        a_add_dir = QAction("Add images from folder...", self)
        a_add_dir.setShortcut("Ctrl+Shift+I")
        a_add_dir.triggered.connect(self.add_images_from_folder)
        m_img.addAction(a_add_file); m_img.addAction(a_add_url); m_img.addAction(a_add_dir)
        m_img.addSeparator()
        a_find_dups = QAction("Find duplicates...", self)
        a_find_dups.setShortcut("Ctrl+D")
        a_find_dups.triggered.connect(self.find_duplicates)
        m_img.addAction(a_find_dups)

        # View
        m_view = mb.addMenu("&View")
        a_fit = QAction("Fit to view", self); a_fit.setShortcut("F")
        a_fit.triggered.connect(self.canvas.fit_image)
        a_zin = QAction("Zoom in", self); a_zin.setShortcut("Ctrl++")
        a_zin.triggered.connect(self.canvas.zoom_in)
        a_zout = QAction("Zoom out", self); a_zout.setShortcut("Ctrl+-")
        a_zout.triggered.connect(self.canvas.zoom_out)
        m_view.addAction(a_fit); m_view.addAction(a_zin); m_view.addAction(a_zout)

        # Labels
        m_lbl = mb.addMenu("&Labels")
        a_lbl_mgr = QAction("Manage labels...", self); a_lbl_mgr.setShortcut("Ctrl+L")
        a_lbl_mgr.triggered.connect(self.open_label_manager)
        m_lbl.addAction(a_lbl_mgr)

        # Help
        m_help = mb.addMenu("&Help")
        a_about = QAction("About Easinotate", self)
        a_about.triggered.connect(self.show_about)
        a_short = QAction("Keyboard shortcuts", self)
        a_short.triggered.connect(self.show_shortcuts)
        m_help.addAction(a_short); m_help.addAction(a_about)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)

        s = self.style()
        def add(act_text, slot, icon=None, shortcut=None, tip=None):
            a = QAction(act_text, self)
            if icon: a.setIcon(s.standardIcon(icon))
            if shortcut: a.setShortcut(shortcut)
            if tip: a.setToolTip(tip)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        add("New", self.new_dataset, QStyle.StandardPixmap.SP_FileIcon, "Ctrl+N", "New dataset")
        add("Open", self.open_dataset, QStyle.StandardPixmap.SP_DirIcon, "Ctrl+O", "Open dataset")
        add("Save", self.save_dataset, QStyle.StandardPixmap.SP_DialogSaveButton, "Ctrl+S", "Save dataset")
        tb.addSeparator()
        add("Add File", self.add_image_from_file, QStyle.StandardPixmap.SP_FileDialogStart, "Ctrl+I", "Add image from file")
        add("Add URL", self.add_image_from_url, QStyle.StandardPixmap.SP_ComputerIcon, "Ctrl+U", "Add image from URL")
        add("Folder", self.add_images_from_folder, QStyle.StandardPixmap.SP_DirOpenIcon, "Ctrl+Shift+I", "Add all images in a folder (recursively)")
        tb.addSeparator()
        add("Fit", self.canvas.fit_image, QStyle.StandardPixmap.SP_DesktopIcon, "F", "Fit image to view")
        tb.addSeparator()
        add("Export", self.export_dataset, QStyle.StandardPixmap.SP_DialogSaveButton, "Ctrl+E", "Export dataset")

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lbl_status = QLabel("Ready")
        self.lbl_count = QLabel("")
        self.lbl_count.setProperty("muted", True)
        sb.addWidget(self.lbl_status, 1)
        sb.addPermanentWidget(self.lbl_count)

    # ---------- state updates ----------
    def _update_ui_state(self):
        has_ds = self.dataset is not None
        has_img = self.current_image is not None
        for w in [self.btn_add_file, self.btn_add_url]:
            w.setEnabled(has_ds)
        self.btn_remove_image.setEnabled(has_img)
        self.btn_relabel_box.setEnabled(has_img)
        self.btn_delete_box.setEnabled(has_img)
        self.primary_label_input.setEnabled(has_img)
        self.image_labels_input.setEnabled(has_img)
        self.notes_input.setEnabled(has_img)
        self.act_save.setEnabled(has_ds)
        self.act_export.setEnabled(has_ds)
        self.active_label_combo.setEnabled(has_ds)

        if self.dataset:
            title = f"Easinotate — {self.dataset.name}"
            if self._dirty:
                title += " *"
            self.setWindowTitle(title)
            self.dataset_header.setText(self.dataset.name)
            self.dataset_subtitle.setText(self.dataset.description or "—")
            self.lbl_count.setText(
                f"{len(self.dataset.images)} images · {self.dataset.total_bboxes} boxes · "
                f"{len(self.dataset.label_set)} labels"
            )
        else:
            self.setWindowTitle("Easinotate")
            self.dataset_header.setText("No dataset loaded")
            self.dataset_subtitle.setText("Create or open a dataset to begin")
            self.lbl_count.setText("")

    def _set_dirty(self, dirty=True):
        self._dirty = dirty
        self._update_ui_state()

    # ---------- image list rendering ----------
    def _matches_filter(self, ann: ImageAnnotation) -> bool:
        # 1) free-text search across filename + labels + primary
        q = self._filter_text.strip().lower()
        if q:
            haystack = " ".join([
                ann.image_name.lower(),
                (ann.primary_label or "").lower(),
                " ".join(ann.image_labels).lower(),
                " ".join(b.label or "" for b in ann.bounding_boxes).lower(),
            ])
            if q not in haystack:
                return False

        # 2) status filter
        m = self._filter_mode
        if m == "annotated":
            if not (ann.bounding_boxes or ann.image_labels or ann.primary_label):
                return False
        elif m == "unannotated":
            if ann.bounding_boxes or ann.image_labels or ann.primary_label:
                return False
        elif m == "has_primary":
            if not ann.primary_label:
                return False
        elif m == "no_primary":
            if ann.primary_label:
                return False
        elif m == "from_url":
            if ann.source != "url":
                return False
        return True

    def _refresh_image_list(self):
        """Rebuild the list applying current search / filter / grouping."""
        self.images_list.blockSignals(True)
        self.images_list.clear()

        if not self.dataset:
            self.images_list.blockSignals(False)
            self._update_visible_count(0, 0)
            return

        all_images = self.dataset.images
        visible = [a for a in all_images if self._matches_filter(a)]

        if self._group_mode == "primary":
            # sort by primary_label (empty last), then by name
            visible.sort(key=lambda a: (
                0 if a.primary_label else 1,
                (a.primary_label or "").lower(),
                a.image_name.lower(),
            ))
            current_group: Optional[str] = object()  # sentinel
            for ann in visible:
                key = ann.primary_label or "(uncategorised)"
                if key != current_group:
                    self._add_group_header(key)
                    current_group = key
                self._add_image_row(ann)
        else:
            # flat: preserve insertion order
            for ann in visible:
                self._add_image_row(ann)

        self.images_list.blockSignals(False)
        self._update_visible_count(len(visible), len(all_images))

    def _add_group_header(self, title: str):
        item = QListWidgetItem(f"  {title}")
        item.setFlags(Qt.ItemFlag.NoItemFlags)  # not selectable
        f = item.font()
        f.setBold(True)
        f.setPointSizeF(max(8.0, f.pointSizeF() - 0.5))
        item.setFont(f)
        item.setForeground(QColor("#a6adc8"))
        item.setBackground(QColor("#181825"))
        item.setData(Qt.ItemDataRole.UserRole, None)  # signal: group header
        self.images_list.addItem(item)

    def _add_image_row(self, ann: ImageAnnotation):
        item = QListWidgetItem()
        item.setText(self._image_list_label(ann))
        item.setData(Qt.ItemDataRole.UserRole, ann.id)

        # Tiny thumbnail
        p = self.dataset.absolute_image_path(ann)
        if os.path.exists(p):
            pm = QPixmap(p)
            if not pm.isNull():
                item.setIcon(QIcon(pm.scaled(
                    28, 28,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )))
        # Compact row height
        item.setSizeHint(QSize(0, 36))
        self.images_list.addItem(item)

    def _image_list_label(self, ann: ImageAnnotation) -> str:
        marker = "●" if ann.bounding_boxes or ann.image_labels or ann.primary_label else "○"
        bits = [f"{marker} {ann.image_name}"]
        if ann.primary_label:
            bits.append(ann.primary_label)
        n = len(ann.bounding_boxes)
        bits.append(f"{n} box" if n == 1 else f"{n} boxes")
        return "   ·   ".join(bits)

    def _update_visible_count(self, visible: int, total: int):
        self._visible_count = visible
        if total == 0:
            self.images_count_label.setText("")
        elif visible == total:
            self.images_count_label.setText(
                f"{total} image{'s' if total != 1 else ''}"
            )
        else:
            self.images_count_label.setText(
                f"Showing {visible} of {total}"
            )

    def _on_search_changed(self, text: str):
        self._filter_text = text
        self._refresh_image_list()

    def _on_filter_changed(self, _idx: int):
        self._filter_mode = self.filter_combo.currentData() or "all"
        self._refresh_image_list()

    def _on_group_changed(self, _idx: int):
        self._group_mode = self.group_combo.currentData() or "none"
        self._refresh_image_list()

    def _refresh_labels_combo(self):
        if not self.dataset:
            return
        cur = self.active_label_combo.currentText()
        self.active_label_combo.blockSignals(True)
        self.active_label_combo.clear()
        for lbl in self.dataset.label_set:
            color = self.dataset.get_label_color(lbl)
            self.active_label_combo.addItem(_make_color_icon(color), lbl)
        if cur:
            idx = self.active_label_combo.findText(cur)
            if idx >= 0:
                self.active_label_combo.setCurrentIndex(idx)
            else:
                self.active_label_combo.setEditText(cur)
        self.active_label_combo.blockSignals(False)
        self._on_active_label_changed(self.active_label_combo.currentText())

    def _refresh_bbox_list(self):
        self.bbox_list.blockSignals(True)
        self.bbox_list.clear()
        items = self.canvas.get_bbox_items()
        for item in items:
            li = QListWidgetItem(item.label or "(unlabeled)")
            li.setIcon(_make_color_icon(item.color_hex))
            li.setData(Qt.ItemDataRole.UserRole, item.bbox_id)
            self.bbox_list.addItem(li)
        self.bbox_list.blockSignals(False)

    # ---------- dataset actions ----------
    def new_dataset(self):
        if not self._maybe_save_changes():
            return
        dlg = NewDatasetDialog(self)
        if dlg.exec():
            name, desc, path = dlg.get_result()
            try:
                os.makedirs(path, exist_ok=True)
                ds = Dataset(name=name, description=desc, project_dir=path)
                ds.save()
                self.dataset = ds
                self.current_image = None
                self.canvas.clear_bboxes()
                if self.canvas.pixmap_item:
                    self.canvas._scene.removeItem(self.canvas.pixmap_item)
                    self.canvas.pixmap_item = None
                self._refresh_image_list()
                self._refresh_labels_combo()
                self._refresh_bbox_list()
                self._set_dirty(False)
                self.lbl_status.setText(f"Created dataset at {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create dataset:\n{e}")

    def open_dataset(self):
        if not self._maybe_save_changes():
            return
        d = QFileDialog.getExistingDirectory(self, "Open dataset folder")
        if not d:
            return
        if not os.path.exists(os.path.join(d, "dataset.json")):
            QMessageBox.warning(self, "Not a dataset",
                "The selected folder does not contain a dataset.json file.")
            return
        try:
            self.dataset = Dataset.load(d)
            self.current_image = None
            self.canvas.clear_bboxes()
            if self.canvas.pixmap_item:
                self.canvas._scene.removeItem(self.canvas.pixmap_item)
                self.canvas.pixmap_item = None
            self._refresh_image_list()
            self._refresh_labels_combo()
            self._refresh_bbox_list()
            self._set_dirty(False)
            self.lbl_status.setText(f"Loaded dataset: {self.dataset.name}")
            if self.dataset.images:
                self.images_list.setCurrentRow(0)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load dataset:\n{e}")

    def save_dataset(self):
        if not self.dataset:
            return
        try:
            # commit any pending edits from the canvas back into the data model
            self._commit_canvas_to_image()
            self.dataset.save()
            self._set_dirty(False)
            self.lbl_status.setText("Saved.")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _autosave(self):
        if self.dataset and self._dirty:
            try:
                self._commit_canvas_to_image()
                self.dataset.save()
                self._set_dirty(False)
                self.lbl_status.setText("Auto-saved.")
            except Exception:
                pass  # silent failure for autosave

    def export_dataset(self):
        if not self.dataset:
            return
        # commit current edits first
        self._commit_canvas_to_image()
        self.dataset.save()

        dlg = ExportDialog(self.dataset, self)
        if not dlg.exec():
            return
        opts = dlg.get_options()

        progress = QProgressDialog("Exporting...", None, 0, 0, self)
        progress.setWindowTitle("Easinotate")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()

        try:
            Exporter.export(
                self.dataset,
                opts["path"],
                fmt=opts["format"],
                include_unlabeled=opts["include_unlabeled"],
            )
            progress.close()
            QMessageBox.information(
                self, "Export complete",
                f"Dataset exported to:\n{opts['path']}"
            )
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Export failed", str(e))

    # ---------- image actions ----------
    def add_image_from_file(self):
        if not self.dataset:
            return
        exts = " ".join(f"*{e}" for e in sorted(VALID_EXT))
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add image(s)", "", f"Images ({exts})"
        )
        for f in files:
            self._import_one_path(f)
        if files:
            self._set_dirty(True)
            self._refresh_image_list()
            # select last imported
            self.images_list.setCurrentRow(self.images_list.count() - 1)

    def add_images_from_folder(self):
        if not self.dataset:
            return
        d = QFileDialog.getExistingDirectory(self, "Pick a folder of images")
        if not d:
            return

        # --- options ---
        recursive_ans = QMessageBox.question(
            self, "Recursive scan?",
            "Scan subfolders too?\n\n"
            "• Yes  — walk the entire tree below this folder\n"
            "• No   — import only files directly in this folder",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        recursive = (recursive_ans == QMessageBox.StandardButton.Yes)

        use_folders_as_label = False
        if recursive:
            ans = QMessageBox.question(
                self, "Use folder names as primary labels?",
                "Use each image's relative folder path as its primary label?\n\n"
                "Example:  fans/ceiling/img.jpg  →  primary_label = 'fans/ceiling'\n\n"
                "This is the easy way to bulk-categorise a pre-sorted folder tree.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            use_folders_as_label = (ans == QMessageBox.StandardButton.Yes)

        # --- scan ---
        paths = scan_folder(d, recursive=recursive)
        if not paths:
            QMessageBox.information(self, "No images", "No supported image files found.")
            return

        # --- import with progress ---
        prog = QProgressDialog(
            f"Importing 0 / {len(paths)}...", "Cancel", 0, len(paths), self
        )
        prog.setWindowTitle("Easinotate")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(200)

        added = 0
        failed: list[tuple[str, str]] = []  # (path, reason)

        for i, path in enumerate(paths):
            if prog.wasCanceled():
                break
            prog.setValue(i)
            prog.setLabelText(f"Importing {i + 1} / {len(paths)}...\n{os.path.basename(path)}")
            QApplication.processEvents()

            primary = derive_primary_label(path, d) if use_folders_as_label else ""
            ok, err = self._import_one_path_silent(path, primary_label=primary)
            if ok:
                added += 1
            else:
                failed.append((path, err))

        prog.setValue(len(paths))
        prog.close()

        if added:
            self._set_dirty(True)
            self._refresh_image_list()

        # --- summary ---
        msg = f"Imported {added} of {len(paths)} image(s)."
        if failed:
            preview = "\n".join(
                f"• {os.path.basename(p)}: {reason}"
                for p, reason in failed[:5]
            )
            extra = f"\n\n...and {len(failed) - 5} more." if len(failed) > 5 else ""
            QMessageBox.warning(
                self, "Folder import",
                f"{msg}\n\n{len(failed)} file(s) failed:\n{preview}{extra}"
            )
        else:
            self.lbl_status.setText(msg)

    def _import_one_path_silent(
        self, path: str, primary_label: str = ""
    ) -> tuple[bool, str]:
        """Import without popping a dialog on every failure. Returns (ok, error_msg)."""
        try:
            stored, w, h = import_from_path(path, self.dataset.images_dir())
            ann = ImageAnnotation(
                image_path=os.path.join("images", stored),
                image_name=stored,
                width=w, height=h,
                source="file", source_url=path,
                primary_label=primary_label,
            )
            self.dataset.add_image(ann)
            return True, ""
        except ImageLoadError as e:
            return False, str(e)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def find_duplicates(self):
        if not self.dataset or not self.dataset.images:
            QMessageBox.information(
                self, "Find duplicates", "Load a dataset with images first."
            )
            return
        # Commit any pending canvas edits so they're reflected in the scan
        self._commit_canvas_to_image()

        dlg = DuplicatesDialog(self.dataset, self)
        if dlg.exec() and dlg.removed_ids:
            removed = len(dlg.removed_ids)
            # If the currently-displayed image was just removed, clear the canvas.
            if self.current_image and self.current_image.id in dlg.removed_ids:
                self.current_image = None
                self.canvas.clear_bboxes()
                self._refresh_bbox_list()
            self._set_dirty(True)
            self._refresh_image_list()
            self.dataset.save()
            self.lbl_status.setText(f"Removed {removed} duplicate image(s).")

    def add_image_from_url(self):
        if not self.dataset:
            return
        dlg = URLImportDialog(self)
        if not dlg.exec():
            return
        url = dlg.get_url()
        if not url:
            return
        try:
            stored, w, h = import_from_url(url, self.dataset.images_dir())
            ann = ImageAnnotation(
                image_path=os.path.join("images", stored),
                image_name=stored,
                width=w, height=h,
                source="url", source_url=url,
            )
            self.dataset.add_image(ann)
            self._set_dirty(True)
            self._refresh_image_list()
            self.images_list.setCurrentRow(self.images_list.count() - 1)
            self.lbl_status.setText(f"Imported from URL: {stored}")
        except ImageLoadError as e:
            QMessageBox.warning(self, "Import failed", str(e))

    def _import_one_path(self, path: str) -> bool:
        try:
            stored, w, h = import_from_path(path, self.dataset.images_dir())
            ann = ImageAnnotation(
                image_path=os.path.join("images", stored),
                image_name=stored,
                width=w, height=h,
                source="file", source_url=path,
            )
            self.dataset.add_image(ann)
            return True
        except ImageLoadError as e:
            QMessageBox.warning(self, "Import failed", f"{path}\n\n{e}")
            return False

    def remove_current_image(self):
        if not self.current_image:
            return
        ans = QMessageBox.question(
            self, "Remove image",
            f"Remove '{self.current_image.image_name}' from this dataset?\n\n"
            "The image file will be deleted from disk on next save.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        # try to remove from disk
        path = self.dataset.absolute_image_path(self.current_image)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
        self.dataset.remove_image(self.current_image.id)
        self.current_image = None
        self.canvas.clear_bboxes()
        if self.canvas.pixmap_item:
            self.canvas._scene.removeItem(self.canvas.pixmap_item)
            self.canvas.pixmap_item = None
        self._set_dirty(True)
        self._refresh_image_list()

    # ---------- selection handlers ----------
    def _on_image_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        # Save edits for previous image first
        if previous is not None:
            self._commit_canvas_to_image()
        # Group-header rows have UserRole == None — treat as no selection
        if current is None or current.data(Qt.ItemDataRole.UserRole) is None:
            self.current_image = None
            self.canvas.clear_bboxes()
            self._refresh_bbox_list()
            self._update_ui_state()
            return

        image_id = current.data(Qt.ItemDataRole.UserRole)
        ann = self.dataset.get_image(image_id) if self.dataset else None
        if not ann:
            return
        self.current_image = ann
        # load image into canvas
        path = self.dataset.absolute_image_path(ann)
        if os.path.exists(path):
            pm = QPixmap(path)
            self.canvas.load_image(pm)
            self.canvas.clear_bboxes()
            for bb in ann.bounding_boxes:
                # ensure color matches dataset palette if a label exists
                if bb.label and bb.label in self.dataset.label_colors:
                    bb.color = self.dataset.label_colors[bb.label]
                self.canvas.add_bbox(bb)
        else:
            QMessageBox.warning(self, "Missing image", f"Image file not found:\n{path}")

        # populate side-panel fields
        self.primary_label_input.blockSignals(True)
        self.primary_label_input.setText(ann.primary_label)
        self.primary_label_input.blockSignals(False)
        self.image_labels_input.blockSignals(True)
        self.image_labels_input.setText(", ".join(ann.image_labels))
        self.image_labels_input.blockSignals(False)
        self.notes_input.blockSignals(True)
        self.notes_input.setPlainText(ann.notes)
        self.notes_input.blockSignals(False)

        self._refresh_bbox_list()
        self._update_ui_state()

    def _commit_canvas_to_image(self):
        if not self.current_image:
            return
        self.current_image.bounding_boxes = self.canvas.get_bboxes()
        # primary_label / image_labels / notes are already saved through field handlers
        self.dataset.touch()
        self._refresh_image_list_item(self.current_image)

    def _refresh_image_list_item(self, ann: ImageAnnotation):
        for i in range(self.images_list.count()):
            it = self.images_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == ann.id:
                it.setText(self._image_list_label(ann))
                return

    # ---------- label & bbox handlers ----------
    def _on_active_label_changed(self, text: str):
        text = (text or "").strip()
        if self.dataset and text and text not in self.dataset.label_colors:
            self.dataset.set_label_color(text, _next_palette_color(self.dataset))
            self._set_dirty(True)
        self.canvas.current_label = text
        if self.dataset and text:
            self.canvas.current_color = self.dataset.get_label_color(text)
        else:
            self.canvas.current_color = "#ff3344"
        # also refresh combo's color icon
        if self.dataset and text:
            idx = self.active_label_combo.findText(text)
            if idx >= 0:
                self.active_label_combo.setItemIcon(idx, _make_color_icon(self.canvas.current_color))

    def _on_bbox_created(self, item: BBoxItem):
        # If there's a single bbox and no image-level label, suggest using its label as primary
        self._set_dirty(True)
        self._refresh_bbox_list()

    def _on_bbox_changed(self, item: BBoxItem):
        self._set_dirty(True)

    def _on_bbox_deleted(self, bbox_id: str):
        self._set_dirty(True)
        self._refresh_bbox_list()

    def _on_bbox_selected_in_canvas(self, item):
        if item is None:
            self.bbox_list.clearSelection()
            return
        for i in range(self.bbox_list.count()):
            li = self.bbox_list.item(i)
            if li.data(Qt.ItemDataRole.UserRole) == item.bbox_id:
                self.bbox_list.setCurrentItem(li)
                return

    def _on_bbox_list_selected(self, current, previous):
        if current is None:
            return
        bbox_id = current.data(Qt.ItemDataRole.UserRole)
        self.canvas.select_bbox(bbox_id)

    def _relabel_selected_bbox(self):
        item = self.bbox_list.currentItem()
        if not item:
            return
        bbox_id = item.data(Qt.ItemDataRole.UserRole)
        target = None
        for it in self.canvas.get_bbox_items():
            if it.bbox_id == bbox_id:
                target = it
                break
        if target is None:
            return
        # offer the existing labels and free entry
        labels = list(self.dataset.label_set) if self.dataset else []
        cur_label = target.label
        new_label, ok = QInputDialog.getItem(
            self, "Relabel box", "Label:", labels, max(0, labels.index(cur_label)) if cur_label in labels else 0,
            editable=True
        )
        if not ok:
            return
        new_label = new_label.strip()
        target.label = new_label
        if new_label:
            if new_label not in self.dataset.label_colors:
                self.dataset.set_label_color(new_label, _next_palette_color(self.dataset))
            target.color_hex = self.dataset.get_label_color(new_label)
        target.update()
        self._refresh_labels_combo()
        self._refresh_bbox_list()
        self._set_dirty(True)

    def _delete_selected_bbox(self):
        item = self.bbox_list.currentItem()
        if not item:
            return
        bbox_id = item.data(Qt.ItemDataRole.UserRole)
        self.canvas.remove_bbox(bbox_id)
        self._refresh_bbox_list()
        self._set_dirty(True)

    def _save_primary_label(self):
        if not self.current_image:
            return
        new_val = self.primary_label_input.text().strip()
        if new_val != self.current_image.primary_label:
            self.current_image.primary_label = new_val
            self._set_dirty(True)
            self._refresh_image_list_item(self.current_image)

    def _save_image_labels(self):
        if not self.current_image:
            return
        raw = self.image_labels_input.text()
        items = [x.strip() for x in raw.split(",") if x.strip()]
        if items != self.current_image.image_labels:
            self.current_image.image_labels = items
            for lbl in items:
                if lbl not in self.dataset.label_colors:
                    self.dataset.set_label_color(lbl, _next_palette_color(self.dataset))
            self._refresh_labels_combo()
            self._set_dirty(True)
            self._refresh_image_list_item(self.current_image)

    def _save_notes(self):
        if not self.current_image:
            return
        new_val = self.notes_input.toPlainText()
        if new_val != self.current_image.notes:
            self.current_image.notes = new_val
            self._set_dirty(True)

    def open_label_manager(self):
        if not self.dataset:
            return
        dlg = LabelEditorDialog(self.dataset, self)
        dlg.exec()
        self._refresh_labels_combo()
        self._set_dirty(True)

    # ---------- help ----------
    def show_about(self):
        AboutDialog(APP_VERSION, self).exec()

    def show_shortcuts(self):
        QMessageBox.information(
            self, "Keyboard shortcuts",
            "<h3>Keyboard shortcuts</h3>"
            "<table cellpadding=4>"
            "<tr><td><b>Ctrl+N</b></td><td>New dataset</td></tr>"
            "<tr><td><b>Ctrl+O</b></td><td>Open dataset</td></tr>"
            "<tr><td><b>Ctrl+S</b></td><td>Save</td></tr>"
            "<tr><td><b>Ctrl+E</b></td><td>Export...</td></tr>"
            "<tr><td><b>Ctrl+I</b></td><td>Add image from file</td></tr>"
            "<tr><td><b>Ctrl+U</b></td><td>Add image from URL</td></tr>"
            "<tr><td><b>Ctrl+L</b></td><td>Manage labels</td></tr>"
            "<tr><td><b>F</b></td><td>Fit image to view</td></tr>"
            "<tr><td><b>Mouse wheel</b></td><td>Zoom in/out</td></tr>"
            "<tr><td><b>Middle-click drag</b></td><td>Pan canvas</td></tr>"
            "<tr><td><b>Drag on image</b></td><td>Draw a new bounding box</td></tr>"
            "<tr><td><b>Click box</b></td><td>Select / move / resize</td></tr>"
            "<tr><td><b>Delete</b></td><td>Remove selected box</td></tr>"
            "</table>"
        )

    # ---------- close ----------
    def closeEvent(self, event):
        if self._maybe_save_changes():
            event.accept()
        else:
            event.ignore()

    def _maybe_save_changes(self) -> bool:
        if not self.dataset or not self._dirty:
            return True
        ans = QMessageBox.question(
            self, "Unsaved changes",
            "You have unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if ans == QMessageBox.StandardButton.Save:
            self.save_dataset()
            return True
        if ans == QMessageBox.StandardButton.Discard:
            return True
        return False