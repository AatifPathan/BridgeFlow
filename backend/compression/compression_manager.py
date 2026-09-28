"""
Bridge Flow - Compression Manager (Phase 8)

Wraps Python's built-in zipfile module. ZIP was chosen deliberately
(over something like 7z or tar.xz) because it's cross-platform with
zero extra dependencies - both a Windows and Linux peer can always
open/create one without installing anything extra.

Compression is written to disk incrementally (zipfile streams each
file's bytes rather than holding the whole archive in memory), which
matters on an 8GB RAM / low-power CPU laptop when zipping large folders.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("compression")

# File extensions that are already compressed - zipping them further
# rarely saves meaningful space and just burns CPU time for nothing.
ALREADY_COMPRESSED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".mp4", ".mkv", ".mov", ".avi", ".mp3", ".zip", ".rar", ".7z",
}


@dataclass
class CompressionResult:
    archive_path: Path
    original_size: int
    compressed_size: int

    @property
    def space_saved_bytes(self) -> int:
        return max(0, self.original_size - self.compressed_size)

    @property
    def space_saved_percent(self) -> float:
        if self.original_size == 0:
            return 0.0
        return round((self.space_saved_bytes / self.original_size) * 100, 2)


def _get_directory_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def should_warn_low_gain(path: Path) -> bool:
    """
    Heuristic used by the UI to warn the user before they compress
    something unlikely to shrink (e.g. a folder of JPEGs/MP4s).
    Does not block compression - just informs the choice.
    """
    if path.is_file():
        return path.suffix.lower() in ALREADY_COMPRESSED_EXTENSIONS
    if path.is_dir():
        files = list(path.rglob("*"))
        if not files:
            return False
        already_compressed = sum(
            1 for f in files if f.is_file() and f.suffix.lower() in ALREADY_COMPRESSED_EXTENSIONS
        )
        return already_compressed / max(1, len(files)) > 0.6
    return False


def compress_to_zip(source_path: Path, output_zip_path: Path, mode: str = "standard") -> CompressionResult:
    """
    mode: "none" | "standard" | "max"
      - "none"     -> ZIP_STORED (archive only, no compression - still
                       useful because it turns a folder into ONE file,
                       which simplifies transfer/resume logic downstream)
      - "standard" -> ZIP_DEFLATED, default compresslevel
      - "max"      -> ZIP_DEFLATED, compresslevel=9
    """
    compression_type = zipfile.ZIP_STORED if mode == "none" else zipfile.ZIP_DEFLATED
    compresslevel = None
    if compression_type == zipfile.ZIP_DEFLATED:
        compresslevel = 9 if mode == "max" else 6

    original_size = (
        source_path.stat().st_size if source_path.is_file() else _get_directory_size(source_path)
    )

    zip_kwargs = {"compression": compression_type, "strict_timestamps": False}
    if compresslevel is not None:
        zip_kwargs["compresslevel"] = compresslevel

    with zipfile.ZipFile(output_zip_path, "w", **zip_kwargs) as zf:
        if source_path.is_file():
            zf.write(source_path, arcname=source_path.name)
        else:
            for file_path in source_path.rglob("*"):
                if file_path.is_file():
                    # Preserve folder structure relative to the selected folder
                    arcname = Path(source_path.name) / file_path.relative_to(source_path)
                    zf.write(file_path, arcname=str(arcname))

    compressed_size = output_zip_path.stat().st_size

    logger.info(
        f"Compressed '{source_path.name}' ({original_size} -> {compressed_size} bytes, mode={mode})"
    )

    return CompressionResult(
        archive_path=output_zip_path,
        original_size=original_size,
        compressed_size=compressed_size,
    )


def extract_zip(zip_path: Path, destination_dir: Path) -> Path:
    """Extracts the archive, restoring the original folder structure."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(destination_dir)
    return destination_dir
