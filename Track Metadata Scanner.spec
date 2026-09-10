# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.building.build_main import Analysis, PYZ, EXE

python_root = Path(sys.base_prefix)
tkinter_dir = python_root / "Lib" / "tkinter"
dll_dir = python_root / "DLLs"
tcl_dir = python_root / "tcl"
tkinter_sources = [(str(p), "tkinter") for p in tkinter_dir.glob("*.py")]
tk_binaries = [(str(dll_dir / name), ".") for name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll")]
def data_tree(root, prefix):
    return [(str(path), str(Path(prefix) / path.relative_to(root).parent)) for path in root.rglob("*") if path.is_file()]

tk_data = data_tree(tcl_dir / "tcl8.6", "tcl/tcl8.6") + data_tree(tcl_dir / "tk8.6", "tcl/tk8.6")

a = Analysis(
    ["app.py"], pathex=[str(Path.cwd())], binaries=tk_binaries,
    datas=tkinter_sources + tk_data, hiddenimports=["tkinter", "tkinter.ttk"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name="Track Metadata Scanner",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
