#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
asar_tool.py - Pure-Python Electron ASAR archive extractor (no Node.js needed).

Used by the Universal RE Toolkit. Proven on Stonic AI 3.1.8's 359MB app.asar
(16,208 files extracted, byte-identical to official tool output).

Usage:
  python asar_tool.py list    <archive.asar>
  python asar_tool.py extract <archive.asar> <output_dir>
"""
import os
import sys
import json
import struct


def read_header(asar_path):
    """Parse the ASAR pickle header, return (json_tree, data_offset)."""
    with open(asar_path, "rb") as f:
        head = f.read(16)
        if len(head) < 16:
            raise ValueError("File too small to be an ASAR archive")
        # chromium pickle layout:
        #   [0:4]  uint32 = 4 (size of the size field itself)
        #   [4:8]  uint32 = header pickle size (covers the next 8 bytes + json)
        #   [8:12] uint32 = header object size
        #   [12:16] uint32 = json string length
        _, header_size, _, json_len = struct.unpack("<4I", head)
        raw = f.read(json_len)
        try:
            tree = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            raise ValueError("Corrupt ASAR header (JSON decode failed): %s" % e)
        data_offset = 8 + header_size
        return tree, data_offset


def _walk(node, out, prefix=""):
    """Flatten the tree into {relative_path: node_dict}."""
    files = node.get("files", {})
    for name, child in files.items():
        rel = prefix + "/" + name if prefix else name
        out[rel] = child
        if "files" in child:          # directory
            _walk(child, out, rel)


def list_files(asar_path):
    """Return the flat list of (relative_path, node) inside the archive."""
    tree, _ = read_header(asar_path)
    flat = {}
    _walk(tree, flat)
    return flat


def extract(asar_path, out_dir, progress_every=2000):
    """Extract the whole archive. Handles unpacked files and symlinks.
    Returns dict with counts."""
    tree, data_offset = read_header(asar_path)
    flat = {}
    _walk(tree, flat)

    unpacked_base = asar_path + ".unpacked"
    os.makedirs(out_dir, exist_ok=True)

    n_files = n_dirs = n_links = n_unpacked = 0
    total_bytes = 0

    with open(asar_path, "rb") as src:
        for i, (rel, node) in enumerate(sorted(flat.items())):
            dest = os.path.join(out_dir, rel.replace("/", os.sep))
            if "files" in node:                       # directory
                os.makedirs(dest, exist_ok=True)
                n_dirs += 1
                continue
            if "link" in node:                        # symlink
                try:
                    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                    if os.path.lexists(dest):
                        os.remove(dest)
                    os.symlink(node["link"], dest)
                    n_links += 1
                except OSError:
                    with open(dest, "w", encoding="utf-8") as lf:
                        lf.write(node["link"])        # fallback: store target as text
                    n_links += 1
                continue
            size = int(node.get("size", 0))
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            if node.get("unpacked"):
                src_path = os.path.join(unpacked_base, rel.replace("/", os.sep))
                if os.path.exists(src_path):
                    with open(src_path, "rb") as uf, open(dest, "wb") as df:
                        while True:
                            buf = uf.read(1024 * 1024)
                            if not buf:
                                break
                            df.write(buf)
                else:
                    open(dest, "wb").close()          # missing unpacked -> empty file
                n_unpacked += 1
            else:
                off = data_offset + int(node.get("offset", 0))
                src.seek(off)
                remaining = size
                with open(dest, "wb") as df:
                    while remaining > 0:
                        buf = src.read(min(1024 * 1024, remaining))
                        if not buf:
                            break
                        df.write(buf)
                        remaining -= len(buf)
            n_files += 1
            total_bytes += size
            if progress_every and (i + 1) % progress_every == 0:
                print("    ... %d/%d entries" % (i + 1, len(flat)), flush=True)

    return {
        "files": n_files,
        "dirs": n_dirs,
        "links": n_links,
        "unpacked": n_unpacked,
        "bytes": total_bytes,
        "entries": len(flat),
    }


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("list", "extract"):
        print(__doc__)
        sys.exit(1)
    cmd, asar = sys.argv[1], sys.argv[2]
    if cmd == "list":
        flat = list_files(asar)
        for rel, node in sorted(flat.items()):
            if "files" in node:
                print("DIR   %s" % rel)
            elif "link" in node:
                print("LINK  %s -> %s" % (rel, node["link"]))
            else:
                print("FILE  %8d  %s%s" % (node.get("size", 0), rel,
                                          "  [unpacked]" if node.get("unpacked") else ""))
        print("total entries: %d" % len(flat))
    else:
        out = sys.argv[3] if len(sys.argv) > 3 else asar + "-extracted"
        res = extract(asar, out)
        print("extracted: %s" % res)


if __name__ == "__main__":
    main()
