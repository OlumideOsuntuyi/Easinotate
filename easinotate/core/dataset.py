"""Dataset management for Easinotate."""
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
from typing import List, Dict, Optional

from .annotation import ImageAnnotation


DATASET_FILE = "dataset.json"
IMAGES_SUBDIR = "images"
SCHEMA_VERSION = 1


@dataclass
class Dataset:
    """Represents an annotation project / dataset.

    A dataset has a project directory on disk with:
        <project_dir>/
            dataset.json   - all metadata + annotations
            images/        - copies of imported images
    """
    name: str
    description: str = ""
    images: List[ImageAnnotation] = field(default_factory=list)
    label_colors: Dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    modified_at: str = ""
    project_dir: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat(timespec="seconds")
        if not self.modified_at:
            self.modified_at = self.created_at

    # ---------- queries ----------
    @property
    def label_set(self) -> List[str]:
        labels = set()
        for img in self.images:
            labels.update(img.image_labels)
            for bb in img.bounding_boxes:
                if bb.label:
                    labels.add(bb.label)
            if img.primary_label:
                # split hierarchical primary labels into components
                for part in img.primary_label.split("/"):
                    if part.strip():
                        labels.add(part.strip())
        return sorted(labels)

    @property
    def total_bboxes(self) -> int:
        return sum(len(img.bounding_boxes) for img in self.images)

    @property
    def labeled_count(self) -> int:
        return sum(1 for img in self.images if img.bounding_boxes or img.image_labels)

    def get_image(self, image_id: str) -> Optional[ImageAnnotation]:
        for img in self.images:
            if img.id == image_id:
                return img
        return None

    def index_of(self, image_id: str) -> int:
        for i, img in enumerate(self.images):
            if img.id == image_id:
                return i
        return -1

    # ---------- mutations ----------
    def add_image(self, ann: ImageAnnotation):
        self.images.append(ann)
        self.touch()

    def remove_image(self, image_id: str):
        self.images = [i for i in self.images if i.id != image_id]
        self.touch()

    def set_label_color(self, label: str, color: str):
        self.label_colors[label] = color
        self.touch()

    def get_label_color(self, label: str, default: str = "#ff3344") -> str:
        return self.label_colors.get(label, default)

    def touch(self):
        self.modified_at = datetime.now().isoformat(timespec="seconds")

    # ---------- persistence ----------
    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "label_colors": self.label_colors,
            "images": [i.to_dict() for i in self.images],
        }

    @classmethod
    def from_dict(cls, data: dict, project_dir: str = "") -> "Dataset":
        ds = cls(
            name=data["name"],
            description=data.get("description", ""),
            label_colors=data.get("label_colors", {}),
            created_at=data.get("created_at", ""),
            modified_at=data.get("modified_at", ""),
            project_dir=project_dir,
        )
        ds.images = [ImageAnnotation.from_dict(i) for i in data.get("images", [])]
        return ds

    def save(self, project_dir: Optional[str] = None):
        """Persist dataset to disk."""
        if project_dir:
            self.project_dir = project_dir
        if not self.project_dir:
            raise ValueError("Dataset has no project_dir set; cannot save.")

        os.makedirs(self.project_dir, exist_ok=True)
        os.makedirs(os.path.join(self.project_dir, IMAGES_SUBDIR), exist_ok=True)

        path = os.path.join(self.project_dir, DATASET_FILE)
        # Write atomically: write to .tmp then replace
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    @classmethod
    def load(cls, project_dir: str) -> "Dataset":
        path = os.path.join(project_dir, DATASET_FILE)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, project_dir=project_dir)

    def images_dir(self) -> str:
        return os.path.join(self.project_dir, IMAGES_SUBDIR)

    def absolute_image_path(self, ann: ImageAnnotation) -> str:
        """Return the on-disk path for an image annotation."""
        return os.path.join(self.images_dir(), ann.image_name)
