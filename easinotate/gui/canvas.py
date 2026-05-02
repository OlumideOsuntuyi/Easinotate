"""Interactive image canvas: pan, zoom, draw and edit bounding boxes."""
from __future__ import annotations
from typing import List, Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QSizeF
from PyQt6.QtGui import (
    QPixmap, QPen, QBrush, QColor, QPainter, QFont, QFontMetrics, QPainterPath
)
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem,
    QGraphicsPixmapItem, QStyleOptionGraphicsItem, QWidget
)

from ..core.annotation import BoundingBox


HANDLE_SIZE = 8  # pixel size for resize handles (in scene units it scales with zoom)


class BBoxItem(QGraphicsRectItem):
    """A movable, resizable, selectable bounding box with a label tag."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 label: str = "", color: str = "#ff3344", bbox_id: str = ""):
        super().__init__(0, 0, w, h)
        self.setPos(x, y)
        self.bbox_id = bbox_id
        self._label = label
        self._color = QColor(color)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._update_pen_brush()
        self._resizing = False
        self._resize_handle = None
        self._press_pos = None
        self._press_rect = None

    # ---- accessors ----
    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, val: str):
        self._label = val
        self.update()

    @property
    def color_hex(self) -> str:
        return self._color.name()

    @color_hex.setter
    def color_hex(self, hex_str: str):
        self._color = QColor(hex_str)
        self._update_pen_brush()
        self.update()

    def to_bbox(self) -> BoundingBox:
        rect = self.rect()
        pos = self.pos()
        return BoundingBox(
            x=float(rect.x() + pos.x()),
            y=float(rect.y() + pos.y()),
            width=float(rect.width()),
            height=float(rect.height()),
            label=self._label,
            color=self.color_hex,
            id=self.bbox_id or BoundingBox(0, 0, 0, 0).id,
        )

    # ---- visuals ----
    def _update_pen_brush(self):
        pen = QPen(self._color, 2)
        pen.setCosmetic(True)  # keep stroke thickness constant during zoom
        self.setPen(pen)
        fill = QColor(self._color)
        fill.setAlpha(40)
        self.setBrush(QBrush(fill))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        # Selection highlight
        if self.isSelected():
            sel_pen = QPen(QColor("#ffffff"), 2, Qt.PenStyle.DashLine)
            sel_pen.setCosmetic(True)
            painter.setPen(sel_pen)
            painter.setBrush(QBrush(self._color, Qt.BrushStyle.SolidPattern))
            fill = QColor(self._color); fill.setAlpha(60)
            painter.setBrush(fill)
            painter.drawRect(rect)
            # handles
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(self._color, 1))
            for hp in self._handle_points():
                hs = self._handle_size_scene()
                painter.drawRect(QRectF(hp.x() - hs/2, hp.y() - hs/2, hs, hs))
        else:
            super().paint(painter, option, widget)

        # Label tag
        if self._label:
            font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            text_w = metrics.horizontalAdvance(self._label) + 12
            text_h = metrics.height() + 4
            tag_rect = QRectF(rect.x(), rect.y() - text_h, text_w, text_h)
            # Draw outside the box; if no room above, draw inside top edge
            if tag_rect.y() < self.scene().sceneRect().top():
                tag_rect.moveTop(rect.y())
            painter.setBrush(QBrush(self._color))
            painter.setPen(Qt.PenStyle.NoPen)
            path = QPainterPath()
            path.addRoundedRect(tag_rect, 3, 3)
            painter.drawPath(path)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, self._label)

    # ---- resize handles ----
    def _handle_size_scene(self) -> float:
        # Convert HANDLE_SIZE (view px) to scene units using current view transform
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view is None:
            return HANDLE_SIZE
        # The view's transform scale tells us how scene maps to view.
        scale = view.transform().m11() or 1.0
        return HANDLE_SIZE / scale

    def _handle_points(self) -> List[QPointF]:
        r = self.rect()
        return [
            QPointF(r.left(),  r.top()),     # 0 TL
            QPointF(r.center().x(), r.top()),# 1 T
            QPointF(r.right(), r.top()),     # 2 TR
            QPointF(r.right(), r.center().y()),# 3 R
            QPointF(r.right(), r.bottom()),  # 4 BR
            QPointF(r.center().x(), r.bottom()),# 5 B
            QPointF(r.left(),  r.bottom()),  # 6 BL
            QPointF(r.left(),  r.center().y()),# 7 L
        ]

    def _hit_handle(self, scene_pos: QPointF) -> Optional[int]:
        local = self.mapFromScene(scene_pos)
        hs = self._handle_size_scene()
        for i, hp in enumerate(self._handle_points()):
            if QRectF(hp.x() - hs, hp.y() - hs, hs * 2, hs * 2).contains(local):
                return i
        return None

    def hoverMoveEvent(self, event):
        if not self.isSelected():
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            super().hoverMoveEvent(event)
            return
        h = self._hit_handle(self.mapToScene(event.pos()))
        cursor_for = {
            0: Qt.CursorShape.SizeFDiagCursor, 4: Qt.CursorShape.SizeFDiagCursor,
            2: Qt.CursorShape.SizeBDiagCursor, 6: Qt.CursorShape.SizeBDiagCursor,
            1: Qt.CursorShape.SizeVerCursor, 5: Qt.CursorShape.SizeVerCursor,
            3: Qt.CursorShape.SizeHorCursor, 7: Qt.CursorShape.SizeHorCursor,
        }
        if h is not None:
            self.setCursor(cursor_for[h])
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isSelected():
            h = self._hit_handle(event.scenePos())
            if h is not None:
                self._resizing = True
                self._resize_handle = h
                self._press_pos = event.scenePos()
                self._press_rect = QRectF(self.rect())
                self._press_item_pos = QPointF(self.pos())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._press_pos is not None:
            self.prepareGeometryChange()
            scene_now = event.scenePos()
            dx = scene_now.x() - self._press_pos.x()
            dy = scene_now.y() - self._press_pos.y()

            r = QRectF(self._press_rect)
            ix, iy = self._press_item_pos.x(), self._press_item_pos.y()
            new_pos_x, new_pos_y = ix, iy

            h = self._resize_handle
            min_size = 4.0

            if h in (0, 1, 2):  # top edge
                new_pos_y = iy + dy
                r.setHeight(max(min_size, r.height() - dy))
            if h in (4, 5, 6):  # bottom edge
                r.setHeight(max(min_size, r.height() + dy))
            if h in (0, 6, 7):  # left edge
                new_pos_x = ix + dx
                r.setWidth(max(min_size, r.width() - dx))
            if h in (2, 3, 4):  # right edge
                r.setWidth(max(min_size, r.width() + dx))

            r.moveTopLeft(QPointF(0, 0))
            self.setRect(r)
            self.setPos(new_pos_x, new_pos_y)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._resize_handle = None
            self._press_pos = None
            self._press_rect = None
            scene = self.scene()
            if scene:
                view = scene.views()[0] if scene.views() else None
                if view and hasattr(view, "bbox_changed"):
                    view.bbox_changed.emit(self)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # constrain inside scene rect
            new_pos = value
            scene_rect = self.scene().sceneRect()
            r = self.rect()
            new_x = max(scene_rect.left(), min(new_pos.x(), scene_rect.right() - r.width()))
            new_y = max(scene_rect.top(), min(new_pos.y(), scene_rect.bottom() - r.height()))
            return QPointF(new_x, new_y)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            view = self.scene().views()[0] if self.scene().views() else None
            if view and hasattr(view, "bbox_changed"):
                view.bbox_changed.emit(self)
        return super().itemChange(change, value)


class AnnotationCanvas(QGraphicsView):
    """Image canvas with bbox creation, editing, zoom, and pan."""

    bbox_created = pyqtSignal(object)   # BBoxItem
    bbox_changed = pyqtSignal(object)   # BBoxItem
    bbox_selected = pyqtSignal(object)  # BBoxItem or None
    bbox_deleted = pyqtSignal(str)      # bbox_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing |
                            QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QBrush(QColor("#181825")))
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)

        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._image_size = QSizeF(0, 0)

        # drawing state
        self.drawing = False
        self.start_point: Optional[QPointF] = None
        self.temp_rect: Optional[QGraphicsRectItem] = None

        # current style for new boxes
        self.current_color = "#ff3344"
        self.current_label = ""

        # interaction
        self._panning = False
        self._pan_start = None

        self._scene.selectionChanged.connect(self._on_selection_changed)

    # ---------- public API ----------
    def load_image(self, pixmap: QPixmap):
        self._scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setZValue(-1000)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self.pixmap_item)
        self._image_size = QSizeF(pixmap.width(), pixmap.height())
        self._scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))
        self.resetTransform()
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def add_bbox(self, bbox: BoundingBox) -> BBoxItem:
        item = BBoxItem(bbox.x, bbox.y, bbox.width, bbox.height,
                        label=bbox.label, color=bbox.color, bbox_id=bbox.id)
        self._scene.addItem(item)
        return item

    def clear_bboxes(self):
        for item in list(self._scene.items()):
            if isinstance(item, BBoxItem):
                self._scene.removeItem(item)

    def get_bboxes(self) -> List[BoundingBox]:
        return [item.to_bbox() for item in self._scene.items() if isinstance(item, BBoxItem)]

    def get_bbox_items(self) -> List[BBoxItem]:
        return [item for item in self._scene.items() if isinstance(item, BBoxItem)]

    def remove_bbox(self, bbox_id: str):
        for item in self.get_bbox_items():
            if item.bbox_id == bbox_id:
                self._scene.removeItem(item)
                self.bbox_deleted.emit(bbox_id)
                return

    def select_bbox(self, bbox_id: str):
        for item in self.get_bbox_items():
            item.setSelected(item.bbox_id == bbox_id)

    def fit_image(self):
        if self.pixmap_item:
            self.resetTransform()
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self):
        self.scale(1.2, 1.2)

    def zoom_out(self):
        self.scale(1 / 1.2, 1 / 1.2)

    # ---------- mouse handling ----------
    def mousePressEvent(self, event):
        if self.pixmap_item is None:
            super().mousePressEvent(event)
            return

        # middle-click pan or space+drag pan
        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_pan(event)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self._scene.itemAt(scene_pos, self.transform())
            # if clicked an existing bbox or its handle, defer to default behavior
            if isinstance(item, BBoxItem):
                super().mousePressEvent(event)
                return
            # otherwise, start drawing a new box (only if click is inside the image)
            if not self._scene.sceneRect().contains(scene_pos):
                super().mousePressEvent(event)
                return
            self.drawing = True
            self.start_point = scene_pos
            self.temp_rect = QGraphicsRectItem(scene_pos.x(), scene_pos.y(), 0, 0)
            pen = QPen(QColor(self.current_color), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self.temp_rect.setPen(pen)
            fill = QColor(self.current_color); fill.setAlpha(30)
            self.temp_rect.setBrush(QBrush(fill))
            self._scene.addItem(self.temp_rect)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
            return

        if self.drawing and self.temp_rect and self.start_point is not None:
            scene_pos = self.mapToScene(event.pos())
            scene_rect = self._scene.sceneRect()
            scene_pos.setX(max(scene_rect.left(), min(scene_pos.x(), scene_rect.right())))
            scene_pos.setY(max(scene_rect.top(),  min(scene_pos.y(), scene_rect.bottom())))
            x = min(self.start_point.x(), scene_pos.x())
            y = min(self.start_point.y(), scene_pos.y())
            w = abs(scene_pos.x() - self.start_point.x())
            h = abs(scene_pos.y() - self.start_point.y())
            self.temp_rect.setRect(x, y, w, h)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() == Qt.MouseButton.MiddleButton:
            self._end_pan()
            event.accept()
            return

        if self.drawing and event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            if self.temp_rect:
                rect = self.temp_rect.rect()
                self._scene.removeItem(self.temp_rect)
                self.temp_rect = None
                if rect.width() > 5 and rect.height() > 5:
                    bbox = BoundingBox(
                        x=rect.x(), y=rect.y(),
                        width=rect.width(), height=rect.height(),
                        label=self.current_label,
                        color=self.current_color,
                    )
                    item = self.add_bbox(bbox)
                    item.setSelected(True)
                    self.bbox_created.emit(item)
            self.start_point = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier or self.pixmap_item is None:
            zoom_in = event.angleDelta().y() > 0
            factor = 1.15 if zoom_in else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        # Without Ctrl: also use wheel to zoom (more natural for an image annotator)
        zoom_in = event.angleDelta().y() > 0
        factor = 1.15 if zoom_in else 1 / 1.15
        self.scale(factor, factor)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in list(self._scene.selectedItems()):
                if isinstance(item, BBoxItem):
                    bid = item.bbox_id
                    self._scene.removeItem(item)
                    self.bbox_deleted.emit(bid)
            event.accept()
            return
        if event.key() == Qt.Key.Key_F:
            self.fit_image()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Minus:
            self.zoom_out()
            event.accept()
            return
        super().keyPressEvent(event)

    # ---------- pan helpers ----------
    def _start_pan(self, event):
        self._panning = True
        self._pan_start = event.pos()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _end_pan(self):
        self._panning = False
        self._pan_start = None
        self.unsetCursor()

    def _on_selection_changed(self):
        sel = self._scene.selectedItems()
        bbox_items = [i for i in sel if isinstance(i, BBoxItem)]
        self.bbox_selected.emit(bbox_items[0] if bbox_items else None)
