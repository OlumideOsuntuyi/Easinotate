"""Dialog for reviewing and removing duplicate / near-duplicate images."""
from __future__ import annotations

import os
from typing import Dict, List, Set

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QProgressDialog, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..core.dataset import Dataset
from ..core.dedup import DupGroup, find_duplicate_groups, hash_images


_THUMB = 96


class _DupTile(QFrame):
    """One image in a group: thumbnail, name, metadata, remove-checkbox."""

    def __init__(self, image_id: str, dataset: Dataset, suggested_keep: bool, parent=None):
        super().__init__(parent)
        self.image_id = image_id
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background-color: #313244; border-radius: 8px; padding: 4px; }"
            "QLabel { background: transparent; }"
        )

        ann = dataset.get_image(image_id)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(_THUMB, _THUMB)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("background-color: #1e1e2e; border-radius: 4px;")
        if ann is not None:
            p = dataset.absolute_image_path(ann)
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    thumb.setPixmap(pm.scaled(
                        _THUMB, _THUMB,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ))
        layout.addWidget(thumb, 0, Qt.AlignmentFlag.AlignCenter)

        # Filename (elided if long)
        name = ann.image_name if ann else "(missing)"
        name_lbl = QLabel(name)
        name_lbl.setMaximumWidth(_THUMB + 12)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(name_lbl)

        # Meta line
        if ann is not None:
            meta = f"{len(ann.bounding_boxes)} bbox · {ann.primary_label or '—'}"
        else:
            meta = "—"
        meta_lbl = QLabel(meta)
        meta_lbl.setProperty("muted", True)
        meta_lbl.setStyleSheet("font-size: 10px;")
        meta_lbl.setMaximumWidth(_THUMB + 12)
        meta_lbl.setWordWrap(True)
        layout.addWidget(meta_lbl)

        # Suggestion badge
        if suggested_keep:
            badge = QLabel("KEEP")
            badge.setStyleSheet(
                "color: #a6e3a1; font-weight: bold; font-size: 10px;"
                "background: transparent;"
            )
            layout.addWidget(badge)

        # Remove checkbox
        self.remove_cb = QCheckBox("Remove")
        self.remove_cb.setChecked(not suggested_keep)
        layout.addWidget(self.remove_cb)


class _GroupCard(QFrame):
    """One duplicate group rendered as a horizontal strip of tiles."""

    def __init__(self, group: DupGroup, dataset: Dataset, parent=None):
        super().__init__(parent)
        self.group = group
        self.dataset = dataset
        self.tiles: List[_DupTile] = []

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background-color: #1e1e2e; border: 1px solid #45475a;"
            " border-radius: 8px; }"
            "QLabel { background: transparent; }"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        kind = "Exact match" if group.is_exact else f"Similar (dist ≤ {group.sample_distance})"
        title = QLabel(f"{kind}  ·  {len(group.members)} images")
        title.setProperty("subheading", True)
        outer.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)
        for idx, image_id in enumerate(group.members):
            tile = _DupTile(image_id, dataset, suggested_keep=(idx == 0))
            self.tiles.append(tile)
            row.addWidget(tile)
        row.addStretch()
        outer.addLayout(row)

    def ids_to_remove(self) -> Set[str]:
        return {t.image_id for t in self.tiles if t.remove_cb.isChecked()}

    def set_keep(self, image_id: str) -> None:
        for t in self.tiles:
            t.remove_cb.setChecked(t.image_id != image_id)


class DuplicatesDialog(QDialog):
    """Scan, review groups, then remove confirmed duplicates."""

    def __init__(self, dataset: Dataset, parent=None):
        super().__init__(parent)
        self.dataset = dataset
        self.removed_ids: Set[str] = set()
        self._cards: List[_GroupCard] = []

        self.setWindowTitle("Find duplicate images")
        self.resize(880, 640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        # ---- top controls ----
        top = QHBoxLayout()
        top.addWidget(QLabel("Sensitivity:"))
        self.threshold_combo = QComboBox()
        for label, value in [
            ("Strict   (exact + nearly identical)", 3),
            ("Default  (visually similar)", 6),
            ("Loose    (likely-similar)", 10),
        ]:
            self.threshold_combo.addItem(label, value)
        self.threshold_combo.setCurrentIndex(1)
        top.addWidget(self.threshold_combo, 1)
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self._do_scan)
        top.addWidget(self.scan_btn)
        outer.addLayout(top)

        self.status_label = QLabel(
            "Click Scan to look for exact and near-duplicate images. "
            "First image in each group is suggested as the one to keep."
        )
        self.status_label.setProperty("muted", True)
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        # ---- scrollable group list ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_inner = QWidget()
        self.groups_layout = QVBoxLayout(self.scroll_inner)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_layout.setSpacing(10)
        self.groups_layout.addStretch()
        self.scroll.setWidget(self.scroll_inner)
        outer.addWidget(self.scroll, 1)

        # ---- bottom buttons ----
        bot = QHBoxLayout()
        self.btn_keep_first = QPushButton("Keep first in each group")
        self.btn_keep_first.clicked.connect(self._auto_keep_first)
        self.btn_keep_most = QPushButton("Keep most-annotated")
        self.btn_keep_most.clicked.connect(self._auto_keep_most_annotated)
        bot.addWidget(self.btn_keep_first)
        bot.addWidget(self.btn_keep_most)
        bot.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        self.btn_remove = QPushButton("Remove selected")
        self.btn_remove.setProperty("danger", True)
        self.btn_remove.setEnabled(False)
        self.btn_remove.clicked.connect(self._do_remove)
        bot.addWidget(self.btn_close)
        bot.addWidget(self.btn_remove)
        outer.addLayout(bot)

    # ----------------------------------------------------------------
    def _clear_groups(self) -> None:
        for c in self._cards:
            c.setParent(None)
            c.deleteLater()
        self._cards = []

    def _do_scan(self) -> None:
        threshold = self.threshold_combo.currentData()
        items = [(a.id, self.dataset.absolute_image_path(a)) for a in self.dataset.images]
        if not items:
            self.status_label.setText("No images in this dataset.")
            return

        prog = QProgressDialog("Hashing images...", "Cancel", 0, len(items), self)
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(200)

        cancelled = {"flag": False}

        def cb(done: int, total: int) -> None:
            if prog.wasCanceled():
                cancelled["flag"] = True
            prog.setValue(done)
            QApplication.processEvents()

        try:
            hashes = hash_images(items, progress=cb)
        except Exception as e:
            prog.close()
            QMessageBox.critical(self, "Hashing failed", str(e))
            return
        prog.close()

        if cancelled["flag"]:
            self.status_label.setText("Scan cancelled.")
            return

        groups = find_duplicate_groups(hashes, threshold=threshold)
        self._clear_groups()

        if not groups:
            self.status_label.setText(
                f"No duplicates found among {len(items)} image(s)."
            )
            self.btn_remove.setEnabled(False)
            return

        for g in groups:
            card = _GroupCard(g, self.dataset)
            # insert before trailing stretch
            self.groups_layout.insertWidget(self.groups_layout.count() - 1, card)
            self._cards.append(card)

        total_extra = sum(len(c.group.members) - 1 for c in self._cards)
        self.status_label.setText(
            f"Found {len(self._cards)} duplicate group(s) — "
            f"{total_extra} image(s) marked for removal "
            f"(keeping 1 from each group)."
        )
        self.btn_remove.setEnabled(True)

    def _auto_keep_first(self) -> None:
        for c in self._cards:
            if c.group.members:
                c.set_keep(c.group.members[0])

    def _auto_keep_most_annotated(self) -> None:
        for c in self._cards:
            best = None
            best_score = (-1, -1, -1)
            for iid in c.group.members:
                a = self.dataset.get_image(iid)
                if a is None:
                    continue
                score = (
                    len(a.bounding_boxes),
                    len(a.image_labels),
                    1 if a.primary_label else 0,
                )
                if score > best_score:
                    best_score = score
                    best = iid
            if best is not None:
                c.set_keep(best)

    def _do_remove(self) -> None:
        to_remove: Set[str] = set()
        for c in self._cards:
            to_remove |= c.ids_to_remove()
        if not to_remove:
            QMessageBox.information(self, "Nothing to remove", "No images are checked.")
            return

        ans = QMessageBox.question(
            self, "Remove duplicates",
            f"Remove {len(to_remove)} image(s) from the dataset?\n\n"
            "Their files will also be deleted from the dataset's images folder. "
            "This cannot be undone.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        for iid in to_remove:
            ann = self.dataset.get_image(iid)
            if ann is None:
                continue
            p = self.dataset.absolute_image_path(ann)
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
            self.dataset.remove_image(iid)

        self.removed_ids = to_remove
        self.accept()