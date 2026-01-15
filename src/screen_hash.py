import hashlib
from pathlib import Path
from typing import Optional


def compute_image_hash(path: Path, size: int = 32) -> Optional[str]:
    try:
        from PIL import Image
    except Exception:
        Image = None

    if Image is None:
        return _hash_file(path)

    try:
        image = Image.open(path).convert("L").resize((size, size))
    except Exception:
        return _hash_file(path)

    pixels = list(image.getdata())
    if not pixels:
        return None
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if px >= avg else "0" for px in pixels)
    return f"{int(bits, 2):0{size * size // 4}x}"


def _hash_file(path: Path) -> Optional[str]:
    try:
        data = path.read_bytes()
    except Exception:
        return None
    return hashlib.sha256(data).hexdigest()
