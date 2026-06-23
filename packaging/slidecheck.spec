# Run on Windows: uv run pyinstaller packaging/slidecheck.spec
# Produces dist/SlideCheck/SlideCheck.exe
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("tkinterdnd2", "pptx"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    ["../pptx_a11y/gui.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SlideCheck", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SlideCheck")
