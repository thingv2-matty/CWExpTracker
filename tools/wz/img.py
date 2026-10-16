"""
Reading inside a .img: the property tree, and the bitmaps hanging off it.

An .img is a nested list of named properties. Most are numbers or strings; the
interesting ones are Canvas nodes, which hold a zlib-compressed bitmap in one of
several pixel formats, sometimes stored at a reduced size and scaled back up.
"""

import zlib

from .archive import Reader

# property type bytes
NIL, I16, I32, F32, F64, STRING, EXTENDED = 0, 2, 3, 4, 5, 8, 9
ALT = {11: I16, 19: I32, 20: I32, 21: I32}       # later aliases for the same


class Node:
    def __init__(self, name, value=None, kind="property"):
        self.name = name
        self.value = value
        self.kind = kind
        self.children = {}
        self.canvas = None

    def __getitem__(self, key):
        node = self
        for part in str(key).split("/"):
            node = node.children[part]
        return node

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def walk(self, prefix=""):
        here = "%s/%s" % (prefix, self.name) if prefix else self.name
        yield here, self
        for child in self.children.values():
            yield from child.walk(here)

    def __repr__(self):
        if self.canvas:
            return "<Canvas %s %dx%d fmt %d>" % (
                self.name, self.canvas["width"], self.canvas["height"],
                self.canvas["format"])
        if self.children:
            return "<%s %s (%d)>" % (self.kind, self.name, len(self.children))
        return "<%s %s = %r>" % (self.kind, self.name, self.value)


def read_img(data, offset, size, name="root"):
    """Parse one .img out of the archive bytes."""
    reader = Reader(data, offset)
    base = offset
    marker = reader.u8()
    if marker == 0x73:
        kind = reader.string()
    elif marker in (0x01, 0x1B):
        here = reader.pos
        reader.pos = base + reader.u32()
        kind = reader.string()
        reader.pos = here + 4
    else:
        raise ValueError("unexpected .img marker 0x%02x" % marker)

    root = Node(name, kind=kind)
    if kind != "Property":
        raise ValueError("unsupported root type %r" % kind)
    reader.u16()
    _read_properties(reader, base, root)
    return root


def _read_properties(reader, base, parent):
    count = reader.compressed_int()
    for _ in range(count):
        name = reader.string_at(base)
        kind = reader.u8()
        kind = ALT.get(kind, kind)

        if kind == NIL:
            parent.children[name] = Node(name, None)
        elif kind == I16:
            parent.children[name] = Node(name, reader.u16())
        elif kind == I32:
            parent.children[name] = Node(name, reader.compressed_int())
        elif kind == F32:
            flag = reader.i8()
            value = reader.f32() if flag == -128 else 0.0
            parent.children[name] = Node(name, value)
        elif kind == F64:
            parent.children[name] = Node(name, reader.f64())
        elif kind == STRING:
            parent.children[name] = Node(name, reader.string_at(base))
        elif kind == EXTENDED:
            length = reader.u32()
            end = reader.pos + length
            node = _read_extended(reader, base, name)
            parent.children[name] = node
            reader.pos = end
        else:
            raise ValueError("unknown property type %d for %r" % (kind, name))


def _read_extended(reader, base, name):
    kind = reader.string_at(base)
    node = Node(name, kind=kind)

    if kind in ("Property", "Shape2D#Convex2D"):
        if kind == "Property":
            reader.u16()
            _read_properties(reader, base, node)
        else:
            for index in range(reader.compressed_int()):
                child = _read_extended(reader, base, str(index))
                node.children[str(index)] = child
    elif kind == "Canvas":
        reader.u8()
        if reader.u8() == 1:
            reader.u16()
            _read_properties(reader, base, node)
        node.canvas = _read_canvas(reader)
    elif kind == "Shape2D#Vector2D":
        node.value = (reader.compressed_int(), reader.compressed_int())
    elif kind == "UOL":
        reader.u8()
        node.value = reader.string_at(base)
    elif kind == "Sound_DX8":
        node.value = "<sound>"
    else:
        node.value = "<unhandled %s>" % kind
    return node


def _read_canvas(reader):
    width = reader.compressed_int()
    height = reader.compressed_int()
    fmt = reader.compressed_int()
    scale = reader.u8()
    reader.u32()
    length = reader.u32()
    reader.u8()
    raw = reader.data[reader.pos:reader.pos + length - 1]
    reader.pos += length - 1
    return {"width": width, "height": height, "format": fmt,
            "scale": scale, "raw": raw}


def inflate(raw):
    """Canvas payloads are zlib, sometimes split into length-prefixed chunks.

    Decompressed incrementally rather than in one call, because these streams
    stop at the last byte of pixel data and omit the adler-32 trailer. The
    one-shot zlib.decompress calls that truncated and raises; a decompress
    object hands back everything it got, which is the full image.
    """
    if raw[:1] == b"\x78":
        engine = zlib.decompressobj()
        out = engine.decompress(raw)
        if out:
            return out

    joined = bytearray()
    pos = 0
    while pos + 4 <= len(raw):
        size = int.from_bytes(raw[pos:pos + 4], "little")
        pos += 4
        joined += raw[pos:pos + size]
        pos += size
    return zlib.decompressobj().decompress(bytes(joined))


def to_image(canvas):
    """Decode a canvas into a PIL RGBA image."""
    from PIL import Image

    width, height = canvas["width"], canvas["height"]
    fmt = canvas["format"] + canvas["scale"]
    data = inflate(canvas["raw"])

    # A scale of n means the bitmap was stored at 1/2**n and is blown back up.
    shrink = 1
    base_fmt = canvas["format"]
    if canvas["scale"] and base_fmt in (1, 2, 513, 517):
        shrink = 1 << canvas["scale"]
    source_w = max(1, width // shrink)
    source_h = max(1, height // shrink)

    if base_fmt == 1:
        image = _argb4444(data, source_w, source_h)
    elif base_fmt == 2:
        image = Image.frombytes("RGBA", (source_w, source_h), data, "raw", "BGRA")
    elif base_fmt == 3:
        image = _argb4444(data, source_w, source_h)
    elif base_fmt == 257:
        image = Image.frombytes("RGBA", (source_w, source_h), data, "raw", "BGRA;15")
    elif base_fmt in (513, 517):
        if base_fmt == 517:
            source_w, source_h = max(1, width // 16), max(1, height // 16)
        image = Image.frombytes("RGB", (source_w, source_h), data,
                                "raw", "BGR;16").convert("RGBA")
    else:
        raise ValueError("unhandled pixel format %d (scale %d)"
                         % (base_fmt, canvas["scale"]))

    if image.size != (width, height):
        image = image.resize((width, height), Image.NEAREST)
    return image


def _argb4444(data, width, height):
    from PIL import Image

    pixels = bytearray(width * height * 4)
    for index in range(width * height):
        packed = data[index * 2] | (data[index * 2 + 1] << 8)
        blue = (packed & 0x0F) * 17
        green = ((packed >> 4) & 0x0F) * 17
        red = ((packed >> 8) & 0x0F) * 17
        alpha = ((packed >> 12) & 0x0F) * 17
        pixels[index * 4:index * 4 + 4] = bytes((red, green, blue, alpha))
    return Image.frombytes("RGBA", (width, height), bytes(pixels))
