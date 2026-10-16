"""
A minimal reader for Wizet PKG1 .wz archives.

Enough to walk the directory tree and pull images out, and no more. Written
because the alternative was downloading an unsigned wz editor from a forum.

    archive.py   the container: header, directory, obfuscated offsets
    img.py       what is inside an .img: properties, and canvases as bitmaps
"""

from .archive import Archive, Entry, Reader
from .img import Node, read_img, to_image

__all__ = ["Archive", "Entry", "Reader", "Node", "read_img", "to_image"]
