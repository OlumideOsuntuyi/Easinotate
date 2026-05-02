"""Annotation data structures for Easinotate."""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import uuid


@dataclass
class BoundingBox:
    """A single bounding box annotation on an image.

    Coordinates are in image pixel space (top-left origin).
    """
    x: float
    y: float
    width: float
    height: float
    label: str = ""
    color: str = "#ff3344"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundingBox":
        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data["height"]),
            label=data.get("label", ""),
            color=data.get("color", "#ff3344"),
            id=data.get("id", str(uuid.uuid4())),
        )

    def to_xyxy(self):
        """Return (x_min, y_min, x_max, y_max)."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def to_yolo(self, img_w: int, img_h: int):
        """Return YOLO format: (x_center, y_center, w, h) normalized."""
        return (
            (self.x + self.width / 2) / img_w,
            (self.y + self.height / 2) / img_h,
            self.width / img_w,
            self.height / img_h,
        )


@dataclass
class ImageAnnotation:
    """All annotation data for a single image."""
    image_path: str  # path within project images/ folder
    image_name: str
    width: int
    height: int
    bounding_boxes: List[BoundingBox] = field(default_factory=list)
    image_labels: List[str] = field(default_factory=list)  # whole-image labels
    primary_label: str = ""  # used for folder categorization (supports "fans/ceiling fans")
    source: str = "file"  # "file" or "url"
    source_url: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "image_path": self.image_path,
            "image_name": self.image_name,
            "width": self.width,
            "height": self.height,
            "bounding_boxes": [b.to_dict() for b in self.bounding_boxes],
            "image_labels": self.image_labels,
            "primary_label": self.primary_label,
            "source": self.source,
            "source_url": self.source_url,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageAnnotation":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            image_path=data["image_path"],
            image_name=data["image_name"],
            width=int(data["width"]),
            height=int(data["height"]),
            bounding_boxes=[BoundingBox.from_dict(b) for b in data.get("bounding_boxes", [])],
            image_labels=data.get("image_labels", []),
            primary_label=data.get("primary_label", ""),
            source=data.get("source", "file"),
            source_url=data.get("source_url", ""),
            notes=data.get("notes", ""),
        )

    @property
    def all_labels(self) -> List[str]:
        """Combined image-level + bbox labels, deduplicated."""
        seen = set()
        out = []
        for lbl in self.image_labels:
            if lbl and lbl not in seen:
                seen.add(lbl)
                out.append(lbl)
        for bb in self.bounding_boxes:
            if bb.label and bb.label not in seen:
                seen.add(bb.label)
                out.append(bb.label)
        return out
