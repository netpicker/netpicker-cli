from pathlib import Path
from netpicker_cli.utils.files import atomic_write

def test_atomic_write_roundtrip(tmp_path: Path):
    dest = tmp_path / "out.txt"
    atomic_write(str(dest), b"hello")
    assert dest.read_text() == "hello"

