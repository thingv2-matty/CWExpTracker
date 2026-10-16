"""
A minimal reader for Wizet PKG1 .wz archives.

Enough to walk the directory tree and pull images out, and no more. Written
because the alternative was downloading an unsigned wz editor from a forum.

The format, briefly:

    header      "PKG1", uint64 data size, uint32 directory start, copyright
    directory   uint16 version check, then a count and that many entries
    entry       a type byte, a name, a size, a checksum and an offset
    offset      obfuscated with a hash derived from the client version, which
                is not stored, so it is brute forced against the version check
    strings     XOR'd with an incrementing mask, and then with a region key.
                This client uses the null key, so only the mask applies.
"""

import struct
import zlib

ASCII_MASK = 0xAA
UNICODE_MASK = 0xAAAA
OFFSET_SEED = 0x581C3F6D
OFFSET_KEY = 0x5F


class Reader:
    def __init__(self, data, start=0):
        self.data = data
        self.pos = start

    def seek(self, pos):
        self.pos = pos

    def u8(self):
        value = self.data[self.pos]
        self.pos += 1
        return value

    def i8(self):
        value = struct.unpack_from("<b", self.data, self.pos)[0]
        self.pos += 1
        return value

    def u16(self):
        value = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return value

    def i32(self):
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def u32(self):
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def i64(self):
        value = struct.unpack_from("<q", self.data, self.pos)[0]
        self.pos += 8
        return value

    def f32(self):
        value = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return value

    def f64(self):
        value = struct.unpack_from("<d", self.data, self.pos)[0]
        self.pos += 8
        return value

    def compressed_int(self):
        """One signed byte, or a sentinel meaning the real value follows."""
        small = self.i8()
        return self.i32() if small == -128 else small

    def compressed_long(self):
        small = self.i8()
        return self.i64() if small == -128 else small

    def string(self):
        """A WZ string: ASCII or UTF-16, each XOR'd with a rolling mask."""
        marker = self.i8()
        if marker == 0:
            return ""
        if marker > 0:                                  # unicode
            length = self.i32() if marker == 127 else marker
            mask = UNICODE_MASK
            out = []
            for _ in range(length):
                out.append(chr(self.u16() ^ mask))
                mask = (mask + 1) & 0xFFFF
            return "".join(out)
        length = self.i32() if marker == -128 else -marker   # ascii
        mask = ASCII_MASK
        out = []
        for _ in range(length):
            out.append(chr(self.u8() ^ mask))
            mask = (mask + 1) & 0xFF
        return "".join(out)

    def string_at(self, base):
        """A name that may be stored once and referenced from several places."""
        kind = self.u8()
        if kind in (0x00, 0x73):
            return self.string()
        if kind in (0x01, 0x1B):
            offset = self.u32()
            here = self.pos
            self.seek(base + offset)
            value = self.string()
            self.seek(here)
            return value
        raise ValueError("unknown string reference 0x%02x at %d"
                         % (kind, self.pos - 1))


def version_hash(version):
    value = 0
    for ch in str(version):
        value = (value * 32 + ord(ch) + 1) & 0xFFFFFFFF
    return value


def version_check(hashed):
    parts = [(hashed >> shift) & 0xFF for shift in (24, 16, 8, 0)]
    check = 0xFF
    for part in parts:
        check ^= part
    return check


def find_versions(expected):
    """Every client version whose hash matches the stored check byte."""
    return [v for v in range(1, 1000)
            if version_check(version_hash(v)) == expected]


def decode_offset(encoded, position, start, hashed):
    """Un-obfuscate a file offset.

    The offset is scrambled with the version hash and its own position, which
    is why the version has to be recovered before anything can be read.
    """
    value = (~(position - start)) & 0xFFFFFFFF
    value = (value * hashed) & 0xFFFFFFFF
    value = (value - OFFSET_SEED) & 0xFFFFFFFF
    shift = value & 0x1F
    value = ((value << shift) | (value >> (32 - shift))) & 0xFFFFFFFF
    value ^= encoded
    value = (value + start * 2) & 0xFFFFFFFF
    return value


class Entry:
    def __init__(self, name, kind, size, checksum, offset, parent):
        self.name = name
        self.kind = kind          # "dir" or "img"
        self.size = size
        self.checksum = checksum
        self.offset = offset
        self.parent = parent
        self.children = []

    @property
    def path(self):
        parts, node = [], self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return "/".join(reversed(parts[:-1])) if len(parts) > 1 else self.name

    def __repr__(self):
        return "<%s %s %d bytes>" % (self.kind, self.path, self.size)


class Archive:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        self._read_header()
        self.root = Entry(path.split("\\")[-1], "dir", 0, 0, self.start, None)
        self._read_directory(self.root, self.start + 2)

    def _read_header(self):
        reader = Reader(self.data)
        if self.data[:4] != b"PKG1":
            raise ValueError("not a PKG1 archive")
        reader.seek(4)
        self.data_size = reader.i64()
        self.start = reader.u32()
        reader.seek(self.start)
        self.check = reader.u16()

        for version in find_versions(self.check):
            hashed = version_hash(version)
            if self._plausible(hashed):
                self.version = version
                self.hash = hashed
                return
        raise ValueError("no client version fits the check byte %d" % self.check)

    def _plausible(self, hashed):
        """Try a candidate version by reading the first entry's offset."""
        try:
            reader = Reader(self.data, self.start + 2)
            count = reader.compressed_int()
            if not 0 < count < 100000:
                return False
            for _ in range(min(count, 3)):
                kind = reader.u8()
                if kind == 1:
                    reader.pos += 10
                    continue
                if kind == 2:
                    reader.i32()
                    kind = reader.u8()
                elif kind in (3, 4):
                    reader.string()
                else:
                    return False
                reader.compressed_int()      # size
                reader.compressed_int()      # checksum
                position = reader.pos
                encoded = reader.u32()
                offset = decode_offset(encoded, position, self.start, hashed)
                if not 0 <= offset < len(self.data):
                    return False
            return True
        except (IndexError, struct.error, ValueError):
            return False

    def _read_directory(self, parent, position):
        reader = Reader(self.data, position)
        count = reader.compressed_int()
        pending = []
        for _ in range(count):
            kind_byte = reader.u8()
            if kind_byte == 1:
                reader.pos += 10
                continue
            if kind_byte == 2:
                where = self.start + 1 + reader.i32()
                here = reader.pos
                reader.seek(where)
                kind_byte = reader.u8()
                name = reader.string()
                reader.seek(here)
            elif kind_byte in (3, 4):
                name = reader.string()
            else:
                raise ValueError("unknown entry type %d" % kind_byte)

            size = reader.compressed_int()
            checksum = reader.compressed_int()
            at = reader.pos
            offset = decode_offset(reader.u32(), at, self.start, self.hash)

            entry = Entry(name, "dir" if kind_byte == 3 else "img",
                          size, checksum, offset, parent)
            parent.children.append(entry)
            if entry.kind == "dir":
                pending.append(entry)

        for entry in pending:
            self._read_directory(entry, entry.offset)

    def walk(self, node=None):
        node = node or self.root
        yield node
        for child in node.children:
            yield from self.walk(child)

    def find(self, needle):
        needle = needle.lower()
        return [e for e in self.walk() if needle in e.name.lower()]
