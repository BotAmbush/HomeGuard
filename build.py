"""
HomeGuard build script
======================
Produces a single self-contained EXE:   dist/HomeGuard.exe

Usage:
    python build.py           # release build (no console window)
    python build.py --debug   # same but keeps a console for error output
"""

from __future__ import annotations

import os
import subprocess
import sys


def get_ffmpeg_data() -> tuple[str, str] | None:
    """Return (src_path, dest_folder_in_bundle) for the bundled ffmpeg binary."""
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()   # downloads if not cached
        print(f"  ffmpeg : {exe}")
        return exe, "imageio_ffmpeg/binaries"
    except Exception as e:
        print(f"  WARNING: Could not locate ffmpeg — audio will require download at runtime: {e}")
        return None


def main() -> None:
    debug = "--debug" in sys.argv

    print("=" * 60)
    print("HomeGuard — PyInstaller build")
    print("=" * 60)

    # ── Ensure PyInstaller is present ──────────────────────────────
    try:
        import PyInstaller  # noqa: F401
        import PyInstaller.__main__ as pi_main
        print(f"  PyInstaller : {PyInstaller.__version__}")
    except ImportError:
        print("  Installing PyInstaller …")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True,
        )
        import PyInstaller.__main__ as pi_main  # noqa: F811

    # ── Locate ffmpeg ───────────────────────────────────────────────
    ffmpeg = get_ffmpeg_data()

    # ── Build argument list ─────────────────────────────────────────
    src_dir = os.path.dirname(os.path.abspath(__file__))

    args: list[str] = [
        "main.py",
        "--name", "HomeGuard",
        "--onefile",
        "--clean",
        "--distpath", src_dir,           # EXE lands in the source folder
        "--workpath", os.path.join(src_dir, "_build_tmp"),  # temp work files
        "--specpath", src_dir,
        # Console / windowed
        *([] if debug else ["--windowed"]),
        # Hidden imports that PyInstaller misses
        "--hidden-import", "PyQt5.QtMultimedia",
        "--hidden-import", "PyQt5.QtMultimediaWidgets",
        "--hidden-import", "PyQt5.sip",
        "--hidden-import", "sounddevice",
        "--hidden-import", "soundfile",
        "--hidden-import", "imageio_ffmpeg",
        "--hidden-import", "pkg_resources.py2_warn",
        # Collect entire packages (data files + DLLs + binaries)
        "--collect-all", "sounddevice",
        "--collect-all", "soundfile",
        "--collect-all", "imageio_ffmpeg",
        "--collect-all", "cv2",
        "--collect-all", "numpy",
        "--collect-all", "certifi",
        "--hidden-import", "certifi",
    ]

    if ffmpeg:
        src, dest = ffmpeg
        sep = ";" if sys.platform == "win32" else ":"
        args += ["--add-data", f"{src}{sep}{dest}"]

    print("\nRunning PyInstaller …\n")
    pi_main.run(args)

    exe = os.path.join(src_dir, "HomeGuard.exe")
    if os.path.exists(exe):
        size_mb = os.path.getsize(exe) / 1_048_576
        print("\n" + "=" * 60)
        print(f"  BUILD SUCCESSFUL")
        print(f"  Output : {exe}")
        print(f"  Size   : {size_mb:.1f} MB")
        print("=" * 60)
        print("\nFiles created next to HomeGuard.exe on first run:")
        print("  telegram.txt  — Telegram bot token & chat ID")
        print("  config.json   — sensitivity / delay settings")
        print("  recordings/   — recorded alert clips")

        import shutil
        tmp = os.path.join(src_dir, "_build_tmp")
        if os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
        spec = os.path.join(src_dir, "HomeGuard.spec")
        if os.path.exists(spec):
            os.remove(spec)
    else:
        print(f"\n❌  Build failed — HomeGuard.exe not found in {src_dir}")
        sys.exit(1)


if __name__ == "__main__":
    main()
