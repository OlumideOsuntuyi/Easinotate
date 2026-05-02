# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Easinotate.

Build (one-file, windowed):
    pyinstaller build_tools/easinotate.spec

Output: dist/Easinotate(.exe)


Why the monkey-patch below exists
---------------------------------
On Python 3.10, the standard library's `dis` module has a bug where
`_get_const_info` can raise `IndexError: tuple index out of range` while
disassembling certain modules' bytecode. PyInstaller's modulegraph
recursively scans every submodule of packages like PIL and PyQt6 to
discover imports, and when it hits one of those modules the entire
build aborts.

The fix in newer PyInstaller releases is to handle that exception. For
older PyInstaller + Python 3.10, we patch it ourselves: catch the
exception, skip the bytecode scan of just that module, and let the
build continue. We don't need that module's imports anyway because we
list everything Easinotate actually uses in `hiddenimports` below.

Best long-term fix is `pip install --upgrade pyinstaller`. This patch
just makes the current setup work without that.
"""

import sys
import warnings
from pathlib import Path


# ---------------------------------------------------------------------------
# Workaround: patch PyInstaller's bytecode iterator to skip modules whose
# disassembly raises on Python 3.10.
# ---------------------------------------------------------------------------
def _patch_pyinstaller_iterate_instructions():
    if sys.version_info[:2] not in {(3, 10)}:
        return  # only needed for 3.10
    try:
        from PyInstaller.lib.modulegraph import util as _mg_util
    except ImportError:
        return

    _original = _mg_util.iterate_instructions

    def _safe_iterate_instructions(code_object):
        try:
            yield from _original(code_object)
        except (IndexError, RuntimeError, AttributeError) as e:
            name = getattr(code_object, "co_name", "<unknown>")
            warnings.warn(
                f"easinotate.spec: skipping bytecode scan of '{name}' "
                f"due to Python 3.10 dis bug ({type(e).__name__}: {e})"
            )
            return

    _mg_util.iterate_instructions = _safe_iterate_instructions


_patch_pyinstaller_iterate_instructions()


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
project_root = Path(SPECPATH).parent
resources_dir = project_root / "easinotate" / "resources"

block_cipher = None


a = Analysis(
    [str(project_root / "easinotate" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(resources_dir / "icon.png"), "easinotate/resources"),
        (str(resources_dir / "icon.ico"), "easinotate/resources"),
    ],
    hiddenimports=[
        # Qt — we want the standard hooks to find these even if scanning fails
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        # Easinotate's own modules — list them explicitly so the build does
        # not depend on PyInstaller's recursive scan succeeding.
        "easinotate",
        "easinotate.main",
        "easinotate.core",
        "easinotate.core.annotation",
        "easinotate.core.dataset",
        "easinotate.core.exporter",
        "easinotate.core.dedup",
        "easinotate.gui",
        "easinotate.gui.canvas",
        "easinotate.gui.dialogs",
        "easinotate.gui.duplicates_dialog",
        "easinotate.gui.main_window",
        "easinotate.gui.style",
        "easinotate.utils",
        "easinotate.utils.image_loader",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy / unused stdlib + science stack
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        # Other Qt bindings we must not pull in
        "PyQt5",
        "PySide2",
        "PySide6",
        # PIL submodules that historically trip the dis bug.
        # We don't use any of them — Pillow's core (PIL.Image) is loaded
        # via the standard PIL hook and is unaffected.
        "PIL.ImageQt",
        "PIL.ImageTk",
        "PIL.ImageShow",
        "PIL._imagingtk",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Easinotate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # windowed app (no console window on Windows)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(resources_dir / "icon.ico"),
)
