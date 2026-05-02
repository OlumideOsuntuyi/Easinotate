"""Export Easinotate datasets to various formats packaged as ZIP files.

Supported formats:
  - "folder"  : Folder-categorized structure (the primary requested format)
  - "coco"    : COCO JSON
  - "yolo"    : YOLO darknet .txt + classes.txt
  - "voc"     : Pascal VOC .xml per image
"""
from __future__ import annotations
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from .dataset import Dataset
from .annotation import ImageAnnotation, BoundingBox


SAFE_RE = re.compile(r"[^\w\-./ ]+")


def _safe_path_part(s: str) -> str:
    """Clean a label so it's safe to use as a folder/file name component."""
    s = SAFE_RE.sub("_", s).strip().strip("/")
    return s or "unlabeled"


def _split_primary(label: str) -> List[str]:
    """Split a primary label like 'fans/ceiling fans' into safe parts."""
    if not label:
        return []
    return [_safe_path_part(p) for p in label.split("/") if p.strip()]


class Exporter:
    """Static-style class with format dispatchers."""

    FORMATS = ("folder", "coco", "yolo", "voc")

    @classmethod
    def export(
        cls,
        dataset: Dataset,
        output_path: str,
        fmt: str = "folder",
        include_unlabeled: bool = True,
    ) -> str:
        fmt = fmt.lower()
        if fmt not in cls.FORMATS:
            raise ValueError(f"Unknown format '{fmt}'. Supported: {cls.FORMATS}")

        if fmt == "folder":
            return cls._export_folder(dataset, output_path, include_unlabeled)
        if fmt == "coco":
            return cls._export_coco(dataset, output_path, include_unlabeled)
        if fmt == "yolo":
            return cls._export_yolo(dataset, output_path, include_unlabeled)
        if fmt == "voc":
            return cls._export_voc(dataset, output_path, include_unlabeled)
        raise AssertionError("unreachable")

    # ---------- helpers ----------
    @staticmethod
    def _resolve_image_path(dataset: Dataset, ann: ImageAnnotation) -> str | None:
        """Return absolute path to image on disk, or None if missing."""
        candidate = dataset.absolute_image_path(ann)
        if os.path.exists(candidate):
            return candidate
        # Fallback to image_path verbatim
        if ann.image_path and os.path.exists(ann.image_path):
            return ann.image_path
        return None

    @staticmethod
    def _build_metadata(dataset: Dataset) -> dict:
        return {
            "name": dataset.name,
            "description": dataset.description,
            "created_at": dataset.created_at,
            "modified_at": dataset.modified_at,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "total_images": len(dataset.images),
            "total_bboxes": dataset.total_bboxes,
            "labels": dataset.label_set,
            "label_colors": dataset.label_colors,
            "exporter": "Easinotate",
        }

    # ---------- format: folder structure ----------
    @classmethod
    def _export_folder(cls, dataset: Dataset, output_path: str, include_unlabeled: bool) -> str:
        """
        Exports a ZIP with structure::

            <dataset_name>/
                metadata.json
                annotations.json          (full machine-readable dump)
                README.txt
                images/
                    <primary_label>/
                        image1.jpg
                        image1.json       (per-image annotation)
                    <parent>/<child>/     (hierarchical labels supported)
                        ...
                    unlabeled/            (if include_unlabeled)
                        ...
        """
        ds_name = _safe_path_part(dataset.name) or "dataset"
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{ds_name}/metadata.json",
                        json.dumps(cls._build_metadata(dataset), indent=2))
            zf.writestr(f"{ds_name}/annotations.json",
                        json.dumps(dataset.to_dict(), indent=2))
            zf.writestr(f"{ds_name}/README.txt", _readme_text(dataset))

            for ann in dataset.images:
                src = cls._resolve_image_path(dataset, ann)
                if not src:
                    continue

                parts = _split_primary(ann.primary_label)
                if not parts:
                    if not include_unlabeled:
                        continue
                    parts = ["unlabeled"]

                folder = "/".join(parts)
                arc_image = f"{ds_name}/images/{folder}/{ann.image_name}"
                zf.write(src, arc_image)

                # per-image sidecar JSON
                stem = Path(ann.image_name).stem
                arc_ann = f"{ds_name}/images/{folder}/{stem}.json"
                zf.writestr(arc_ann, json.dumps(ann.to_dict(), indent=2))

        return output_path

    # ---------- format: COCO ----------
    @classmethod
    def _export_coco(cls, dataset: Dataset, output_path: str, include_unlabeled: bool) -> str:
        ds_name = _safe_path_part(dataset.name) or "dataset"
        labels = dataset.label_set
        # COCO category ids start at 1
        cat_id_map = {lbl: i + 1 for i, lbl in enumerate(labels)}

        coco = {
            "info": {
                "description": dataset.description or dataset.name,
                "version": "1.0",
                "date_created": datetime.now().isoformat(timespec="seconds"),
            },
            "licenses": [],
            "images": [],
            "annotations": [],
            "categories": [
                {"id": cid, "name": lbl, "supercategory": ""}
                for lbl, cid in cat_id_map.items()
            ],
        }

        ann_id = 1
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_id, ann in enumerate(dataset.images, start=1):
                src = cls._resolve_image_path(dataset, ann)
                if not src:
                    continue
                if not include_unlabeled and not ann.bounding_boxes and not ann.image_labels:
                    continue

                coco["images"].append({
                    "id": img_id,
                    "file_name": ann.image_name,
                    "width": ann.width,
                    "height": ann.height,
                })
                zf.write(src, f"{ds_name}/images/{ann.image_name}")

                for bb in ann.bounding_boxes:
                    cid = cat_id_map.get(bb.label)
                    if cid is None:
                        continue
                    coco["annotations"].append({
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": cid,
                        "bbox": [bb.x, bb.y, bb.width, bb.height],
                        "area": bb.width * bb.height,
                        "iscrowd": 0,
                        "segmentation": [],
                    })
                    ann_id += 1

            zf.writestr(f"{ds_name}/annotations.json", json.dumps(coco, indent=2))
            zf.writestr(f"{ds_name}/metadata.json",
                        json.dumps(cls._build_metadata(dataset), indent=2))

        return output_path

    # ---------- format: YOLO ----------
    @classmethod
    def _export_yolo(cls, dataset: Dataset, output_path: str, include_unlabeled: bool) -> str:
        ds_name = _safe_path_part(dataset.name) or "dataset"
        labels = dataset.label_set
        cls_id_map = {lbl: i for i, lbl in enumerate(labels)}

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{ds_name}/classes.txt", "\n".join(labels) + ("\n" if labels else ""))
            zf.writestr(f"{ds_name}/metadata.json",
                        json.dumps(cls._build_metadata(dataset), indent=2))

            # YOLO data.yaml convenience file
            yaml_content = (
                f"# YOLO dataset config exported by Easinotate\n"
                f"path: ./{ds_name}\n"
                f"train: images\n"
                f"val: images\n"
                f"nc: {len(labels)}\n"
                f"names: {labels}\n"
            )
            zf.writestr(f"{ds_name}/data.yaml", yaml_content)

            for ann in dataset.images:
                src = cls._resolve_image_path(dataset, ann)
                if not src:
                    continue
                if not include_unlabeled and not ann.bounding_boxes:
                    continue

                zf.write(src, f"{ds_name}/images/{ann.image_name}")

                lines = []
                for bb in ann.bounding_boxes:
                    cid = cls_id_map.get(bb.label)
                    if cid is None:
                        continue
                    xc, yc, w, h = bb.to_yolo(ann.width, ann.height)
                    lines.append(f"{cid} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

                stem = Path(ann.image_name).stem
                zf.writestr(f"{ds_name}/labels/{stem}.txt", "\n".join(lines))

        return output_path

    # ---------- format: Pascal VOC ----------
    @classmethod
    def _export_voc(cls, dataset: Dataset, output_path: str, include_unlabeled: bool) -> str:
        ds_name = _safe_path_part(dataset.name) or "dataset"

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{ds_name}/metadata.json",
                        json.dumps(cls._build_metadata(dataset), indent=2))

            for ann in dataset.images:
                src = cls._resolve_image_path(dataset, ann)
                if not src:
                    continue
                if not include_unlabeled and not ann.bounding_boxes:
                    continue

                zf.write(src, f"{ds_name}/JPEGImages/{ann.image_name}")
                xml_str = _voc_xml_for(ann, ds_name)
                stem = Path(ann.image_name).stem
                zf.writestr(f"{ds_name}/Annotations/{stem}.xml", xml_str)

        return output_path


def _voc_xml_for(ann: ImageAnnotation, dataset_name: str) -> str:
    root = Element("annotation")
    SubElement(root, "folder").text = dataset_name
    SubElement(root, "filename").text = ann.image_name
    size = SubElement(root, "size")
    SubElement(size, "width").text = str(ann.width)
    SubElement(size, "height").text = str(ann.height)
    SubElement(size, "depth").text = "3"
    SubElement(root, "segmented").text = "0"
    for bb in ann.bounding_boxes:
        if not bb.label:
            continue
        obj = SubElement(root, "object")
        SubElement(obj, "name").text = bb.label
        SubElement(obj, "pose").text = "Unspecified"
        SubElement(obj, "truncated").text = "0"
        SubElement(obj, "difficult").text = "0"
        bndbox = SubElement(obj, "bndbox")
        SubElement(bndbox, "xmin").text = str(int(round(bb.x)))
        SubElement(bndbox, "ymin").text = str(int(round(bb.y)))
        SubElement(bndbox, "xmax").text = str(int(round(bb.x + bb.width)))
        SubElement(bndbox, "ymax").text = str(int(round(bb.y + bb.height)))
    rough = tostring(root, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def _readme_text(dataset: Dataset) -> str:
    return (
        f"Easinotate Dataset Export\n"
        f"=========================\n\n"
        f"Name        : {dataset.name}\n"
        f"Description : {dataset.description}\n"
        f"Created     : {dataset.created_at}\n"
        f"Modified    : {dataset.modified_at}\n"
        f"Total images: {len(dataset.images)}\n"
        f"Total bboxes: {dataset.total_bboxes}\n"
        f"Labels      : {', '.join(dataset.label_set) or '(none)'}\n\n"
        "Folder structure: images are categorized into sub-folders based\n"
        "on each image's primary_label. Hierarchical labels separated by\n"
        "'/' produce nested folders (e.g. 'fans/ceiling fans').\n\n"
        "Each image has a sibling .json file containing the full annotation\n"
        "data (bounding boxes, labels, source, etc).\n"
    )
