"""
Windows-oriented safety tests. They use Windows-style inputs (backslashes,
reserved device names, quoted 'Copy as path' text) but run on any OS.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.filenames import clean_user_path, sanitize_filename, unique_path


def test_traversal_with_backslashes_is_neutralised():
    assert sanitize_filename("..\\..\\Windows\\evil.exe") == "evil.exe"


def test_traversal_with_forward_slashes_is_neutralised():
    assert sanitize_filename("../../etc/passwd") == "passwd"


def test_absolute_windows_path_reduced_to_file_name():
    assert sanitize_filename("C:\\Users\\Aatif\\secret.txt") == "secret.txt"


def test_invalid_windows_characters_replaced():
    assert sanitize_filename('re:port?*<final>|.txt') == "re_port___final__.txt"


def test_reserved_device_names_are_prefixed():
    assert sanitize_filename("NUL") == "_NUL"
    assert sanitize_filename("com1.txt") == "_com1.txt"


def test_dot_names_fall_back_to_default():
    assert sanitize_filename("..") == "received_file"
    assert sanitize_filename("") == "received_file"


def test_normal_names_and_unicode_are_kept():
    assert sanitize_filename("report final.pdf") == "report final.pdf"
    assert sanitize_filename("रिपोर्ट.docx") == "रिपोर्ट.docx"
    assert sanitize_filename(".gitignore") == ".gitignore"


def test_unique_path_never_overwrites(tmp_path):
    original = tmp_path / "photo.jpg"
    original.write_bytes(b"1")
    second = unique_path(original)
    assert second.name == "photo (1).jpg"
    second.write_bytes(b"2")
    assert unique_path(original).name == "photo (2).jpg"


def test_unique_path_returns_same_when_free(tmp_path):
    assert unique_path(tmp_path / "new.txt") == tmp_path / "new.txt"


def test_quoted_copy_as_path_is_cleaned():
    assert clean_user_path('"C:\\Users\\Aatif\\My File.txt"') == Path("C:\\Users\\Aatif\\My File.txt")
    assert clean_user_path("  'some/file.txt'  ") == Path("some/file.txt")
    assert clean_user_path("plain.txt") == Path("plain.txt")
