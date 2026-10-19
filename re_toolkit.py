#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 Universal RE Toolkit v1.0  (by Fahad x Jarvis)
 Reverse-engineer Electron / NSIS / generic installers into a full,
 readable source package - the same proven pipeline that fully extracted
 Stonic AI 3.1.8 (44,653 files, SHA-256 verified 100%).
============================================================================

Pipeline:
  STAGE 0  locate tools (bundled 7-Zip) + hash the installer
  STAGE 1  open the installer with 7-Zip, find the real payload
           (NSIS: $PLUGINSDIR/app-64.7z | portable: resources/app.asar | raw archive)
  STAGE 2  extract the payload into a full application tree
  STAGE 3  extract every *.asar (Electron source archive) - pure Python, no Node
  STAGE 4  build INVENTORY.txt (file categories, largest files, runtimes found)
  STAGE 5  generate SHA256SUMS.txt (every file, git-style)
  STAGE 6  write RE-REPORT.md
  STAGE 7  pack everything into <name>-FULL-RE.zip (+ optional 45MB split parts)

Usage:
  python re_toolkit.py <installer-or-archive> [options]
Options:
  --outdir DIR     output base dir   (default: ./RE-OUTPUT)
  --split          also write 45MB split parts (Stonic-style, copy /b joinable)
  --store          zip without compression (faster)
  --skip-zip       skip final packing

Windows: just drag & drop an installer .exe onto RE-Toolkit.bat
"""
import os
import re
import sys
import json
import time
import shutil
import hashlib
import zipfile
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
MB = 1024 * 1024

CATEGORIES = {
    "executables": {".exe", ".dll", ".sys"},
    "python_source": {".py", ".pyw", ".pyi"},
    "javascript": {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"},
    "web": {".html", ".htm", ".css", ".scss"},
    "node_config": {".json", ".lock"},
    "models_ai": {".task", ".ppn", ".onnx", ".tflite", ".lm", ".bin model", ".engine", ".param", ".caffemodel"},
    "archives": {".zip", ".7z", ".tar", ".gz", ".xz", ".bz2", ".whl", ".asar", ".pak", ".dat"},
    "audio": {".wav", ".mp3", ".ogg", ".flac"},
    "images": {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp"},
    "docs": {".md", ".txt", ".pdf", ".rst", ".chm", ".hlp"},
    "datasets": {".csv", ".tsv", ".db", ".sqlite", ".sqlite3"},
}


def log(msg):
    print(msg, flush=True)


def sha256_file(path, bufsize=8 * MB):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def find_7z():
    """Prefer the bundled full 7-Zip (has NSIS support), then system-wide.
    The bundled binary is a Windows PE - only use it on Windows."""
    if sys.platform == "win32":
        bundled = os.path.join(HERE, "tools", "7z", "7z.exe")
        if os.path.isfile(bundled):
            return bundled
        for name in ("7z", "7za"):
            p = shutil.which(name)
            if p:
                return p
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        cand = os.path.join(pf, "7-Zip", "7z.exe")
        if os.path.isfile(cand):
            return cand
        return None
    # Linux/macOS: prefer modern 7-Zip, then common distro packages.
    for name in ("7zz", "7z", "7za"):
        p = shutil.which(name)
        if p:
            return p
    for cand in ("~/bin/7zz", "~/bin/7z", "/usr/local/bin/7zz",
                 "/usr/local/bin/7z", "/opt/7zz/7zz"):
        cand = os.path.expanduser(cand)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def run_7z(SevenZ, args, workdir=None, quiet=True):
    cmd = [SevenZ] + args
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       cwd=workdir)
    out = r.stdout.decode("utf-8", errors="replace")
    if r.returncode not in (0, 1):        # 1 = warnings (ok for some archives)
        raise RuntimeError("7-Zip failed (%d):\n%s" % (r.returncode, out[-2000:]))
    return out


def pick_inner_payload(listing):
    """From 7z listing text, choose the real payload inside an NSIS installer."""
    names = re.findall(r"^(?:[^\n]*?\s)(\$PLUGINSDIR[\\/][^\s]+\.7z)$", listing, re.M)
    if not names:
        names = re.findall(r"(\$PLUGINSDIR[\\/]app-\d+\.7z)", listing)
    if not names:
        return None, []
    prio = [n for n in names if "app-64" in n.lower()]
    prio += [n for n in names if "app-32" in n.lower()]
    prio += [n for n in sorted(set(names)) if n not in prio]
    return prio[0], sorted(set(names))


def zip_tree(root, zip_path, compresslevel=6, progress_every=500):
    """Zip an entire directory tree with relative paths + progress."""
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=compresslevel) as z:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fn in sorted(filenames):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                try:
                    z.write(full, rel)
                except OSError as e:
                    log("    [zip-skip] %s (%s)" % (rel, e))
                    continue
                n += 1
                if progress_every and n % progress_every == 0:
                    log("    ... %d files zipped" % n)
    return n


def split_file(path, part_mb=45):
    """Split into Stonic-style parts .01 .02 ... and write join instructions."""
    size = os.path.getsize(path)
    chunk = part_mb * MB
    total_parts = (size + chunk - 1) // chunk
    base = os.path.basename(path)
    cmds = []
    with open(path, "rb") as src:
        for i in range(total_parts):
            part = "%s.%02d" % (path, i + 1)
            with open(part, "wb") as dst:
                remaining = min(chunk, size - i * chunk)
                while remaining > 0:
                    b = src.read(min(8 * MB, remaining))
                    if not b:
                        break
                    dst.write(b)
                    remaining -= len(b)
            cmds.append(base + ".%02d" % (i + 1))
            log("    part %02d/%02d written" % (i + 1, total_parts))
    join_cmd = "copy /b " + "+".join(cmds) + " " + base
    with open(path + "-JOIN.txt", "w", encoding="utf-8") as f:
        f.write("HOW TO JOIN (Windows CMD, run in the same folder):\n\n")
        f.write(join_cmd + "\n\nOr simply: right-click %s.01 -> 7-Zip -> Extract Here\n" % base)
    return total_parts


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return "%.1f %s" % (n, u) if u != "B" else "%d B" % n
        n /= 1024.0


# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    src = os.path.abspath(args[0])
    flags = set(a.lower() for a in args[1:])
    outdir_opt = None
    if "--outdir" in args:
        outdir_opt = os.path.abspath(args[args.index("--outdir") + 1])

    if not os.path.isfile(src):
        log("[!] Input not found: %s" % src)
        sys.exit(2)

    SevenZ = find_7z()
    if not SevenZ:
        if os.name == "nt":
            log("[!] 7-Zip not found! Keep tools/7z/ beside re_toolkit.py or install 7-Zip.")
        else:
            log("[!] 7-Zip CLI not found. Install it first:")
            log("    Debian/Ubuntu: sudo apt-get update && sudo apt-get install -y p7zip-full")
            log("    Fedora:       sudo dnf install -y p7zip p7zip-plugins")
            log("    Alpine:       sudo apk add p7zip")
            log("    macOS:        brew install sevenzip   (or install p7zip via Homebrew)")
            log("    Then rerun:   python3 re_toolkit.py <installer-or-archive>")
        sys.exit(3)
    log("[i] 7-Zip: %s" % SevenZ)

    t0 = time.time()
    base_name = re.sub(r"\.(exe|7z|zip|msi)$", "", os.path.basename(src), flags=re.I)
    out_base = outdir_opt or os.path.join(os.path.dirname(HERE), "RE-OUTPUT")
    work = os.path.join(out_base, base_name)
    stage1 = os.path.join(work, "STAGE1-installer-opened")
    appdir = os.path.join(work, "app")
    findings = os.path.join(work, "RE-DOCS")
    for d in (stage1, appdir, findings):
        os.makedirs(d, exist_ok=True)

    report = ["# RE-REPORT - %s" % base_name, "",
              "Generated by Universal RE Toolkit v1.0", ""]

    # ---- STAGE 0: hash installer -----------------------------------------
    log("[STAGE 0] hashing installer ...")
    inst_hash = sha256_file(src)
    inst_size = os.path.getsize(src)
    log("    sha256 = %s" % inst_hash)
    log("    size   = %s" % human(inst_size))
    report += ["## Installer", "", "- file: %s" % os.path.basename(src),
               "- size: %d bytes (%s)" % (inst_size, human(inst_size)),
               "- sha256: `%s`" % inst_hash, ""]

    # ---- STAGE 1: open installer -----------------------------------------
    log("[STAGE 1] opening installer with 7-Zip ...")
    listing = run_7z(SevenZ, ["l", "-ba", src])
    inner, all_inner = pick_inner_payload(listing)
    if inner:
        log("    NSIS payload found: %s" % inner)
        report += ["## Stage 1 - installer opened", "",
                   "- NSIS installer detected, payload: `%s`" % inner, ""]
        run_7z(SevenZ, ["x", "-y", "-o" + stage1, src])
        payload = os.path.join(stage1, inner.replace("$PLUGINSDIR\\", "$PLUGINSDIR/").replace("/", os.sep))
        if not os.path.isfile(payload):
            # find it case-insensitively
            for dp, _, fns in os.walk(stage1):
                for fn in fns:
                    if fn.lower() == os.path.basename(inner).lower():
                        payload = os.path.join(dp, fn)
        log("[STAGE 2] extracting payload %s ..." % os.path.basename(payload))
        run_7z(SevenZ, ["x", "-y", "-o" + appdir, payload])
        report += ["## Stage 2 - payload extracted", "",
                   "- payload extracted to `app/` (%s files total)" %
                   sum(len(f) for _, _, f in os.walk(appdir)), ""]
    else:
        log("    no $PLUGINSDIR/*.7z - checking for portable Electron layout ...")
        run_7z(SevenZ, ["x", "-y", "-o" + stage1, src])
        asars0 = []
        for dp, _, fns in os.walk(stage1):
            asars0 += [os.path.join(dp, fn) for fn in fns if fn.lower().endswith(".asar")]
        if asars0:
            log("    portable layout found (%d asar) - using STAGE1 tree as app/" % len(asars0))
            shutil.rmtree(appdir, ignore_errors=True)
            shutil.move(stage1, appdir)
            os.makedirs(stage1, exist_ok=True)
            open(os.path.join(stage1, "INFO.txt"), "w").write(
                "Installer was a portable/electron layout; app tree moved to ../app\n")
            report += ["## Stage 1/2 - portable layout", "",
                       "- no NSIS payload; application tree extracted directly", ""]
        else:
            log("    generic archive - treating whole content as app tree")
            shutil.rmtree(appdir, ignore_errors=True)
            shutil.move(stage1, appdir)
            os.makedirs(stage1, exist_ok=True)
            open(os.path.join(stage1, "INFO.txt"), "w").write(
                "Generic archive input; content tree moved to ../app\n")
            report += ["## Stage 1/2 - generic archive", "", "- raw archive extracted", ""]

    if not os.listdir(appdir):
        log("[!] app tree is empty - unknown installer format. Report saved.")
        report += ["## WARNING", "", "- no payload could be extracted automatically.", ""]
        with open(os.path.join(findings, "RE-REPORT.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(report))
        sys.exit(4)

    n_app_files = sum(len(f) for _, _, f in os.walk(appdir))
    log("    app tree: %s files" % n_app_files)

    # ---- STAGE 3: extract all .asar ---------------------------------------
    log("[STAGE 3] extracting Electron ASAR archives ...")
    sys.path.insert(0, HERE)
    import asar_tool
    asar_report = []
    for dp, _, fns in os.walk(appdir):
        for fn in fns:
            if not fn.lower().endswith(".asar"):
                continue
            asar_path = os.path.join(dp, fn)
            out_asar = asar_path + "-extracted"
            if os.path.isdir(out_asar) and os.listdir(out_asar):
                log("    skip (already extracted): %s" % os.path.relpath(asar_path, appdir))
                continue
            size = os.path.getsize(asar_path)
            log("    extracting %s (%s) ..." % (os.path.relpath(asar_path, appdir), human(size)))
            try:
                res = asar_tool.extract(asar_path, out_asar)
                asar_report.append((os.path.relpath(asar_path, appdir), size, res))
                log("    -> %s entries (%s files)" % (res["entries"], res["files"]))
            except Exception as e:
                asar_report.append((os.path.relpath(asar_path, appdir), size, None))
                log("    [!] failed: %s" % e)
    report += ["## Stage 3 - ASAR extraction (Electron source)", ""]
    if asar_report:
        for name, size, res in asar_report:
            if res:
                report.append("- `%s` (%s) -> %d files, %d dirs, %d symlinks, %d unpacked"
                              % (name, human(size), res["files"], res["dirs"], res["links"], res["unpacked"]))
            else:
                report.append("- `%s` (%s) -> FAILED" % (name, human(size)))
    else:
        report.append("- no .asar archives found (not an Electron app, or already loose)")
    report.append("")

    # ---- STAGE 4: inventory ------------------------------------------------
    log("[STAGE 4] building inventory ...")
    cat_count = {k: [0, 0] for k in CATEGORIES}
    other = [0, 0]
    big = []
    runtimes = set()
    for dp, dns, fns in os.walk(appdir):
        for fn in fns:
            full = os.path.join(dp, fn)
            try:
                sz = os.path.getsize(full)
            except OSError:
                continue
            ext = os.path.splitext(fn)[1].lower()
            hit = False
            for cat, exts in CATEGORIES.items():
                if ext in exts or (cat == "models_ai" and (fn.endswith(".lm.bin") or "language-model" in fn.lower())):
                    cat_count[cat][0] += 1
                    cat_count[cat][1] += sz
                    hit = True
                    break
            if not hit:
                other[0] += 1
                other[1] += sz
            big.append((sz, os.path.relpath(full, appdir)))
            low = fn.lower()
            if low == "node.exe":
                runtimes.add("Node.js runtime")
            if low.startswith("python") and low.endswith(".exe"):
                runtimes.add("Python runtime (embedded)")
            if low == "package.json":
                try:
                    pj = json.load(open(full, encoding="utf-8", errors="replace"))
                    if isinstance(pj, dict) and pj.get("name"):
                        runtimes.add("App: %s %s" % (pj.get("name"), pj.get("version", "")))
                except Exception:
                    pass
    big.sort(reverse=True)
    inv = ["INVENTORY - %s" % base_name, "=" * 60, "",
           "Total app tree files: %d" % n_app_files, ""]
    if runtimes:
        inv.append("Detected runtimes/apps:")
        inv += ["  - %s" % r for r in sorted(runtimes)]
        inv.append("")
    inv.append("Files by category (count, total size):")
    inv.append("-" * 60)
    for cat, (c, s) in sorted(cat_count.items(), key=lambda kv: -kv[1][1]):
        if c:
            inv.append("  %-16s %6d files   %12s" % (cat, c, human(s)))
    inv.append("  %-16s %6d files   %12s" % ("other", other[0], human(other[1])))
    inv += ["", "Top 30 largest files:", "-" * 60]
    for sz, rel in big[:30]:
        inv.append("  %12s  %s" % (human(sz), rel))
    with open(os.path.join(findings, "INVENTORY.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(inv))
    log("    %d categories written" % len([1 for c, s in cat_count.values() if s]))

    report += ["## Stage 4 - inventory", "",
               "- app tree files: %d" % n_app_files,
               "- runtimes: %s" % (", ".join(sorted(runtimes)) if runtimes else "n/a"), ""]

    # ---- STAGE 5: SHA256SUMS ----------------------------------------------
    log("[STAGE 5] hashing every file (this can take a minute) ...")
    sums_path = os.path.join(findings, "SHA256SUMS.txt")
    n_hashed = 0
    with open(sums_path, "w", encoding="utf-8") as out:
        for dp, dnf, fns in os.walk(work):
            for fn in sorted(fns):
                if fn == "SHA256SUMS.txt":
                    continue
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, work).replace(os.sep, "/")
                try:
                    out.write("%s  %s\n" % (sha256_file(full), rel))
                    n_hashed += 1
                    if n_hashed % 2000 == 0:
                        log("    ... %d files hashed" % n_hashed)
                except OSError:
                    pass
    log("    %d files hashed" % n_hashed)
    report += ["## Stage 5 - integrity", "", "- %d files hashed into RE-DOCS/SHA256SUMS.txt" % n_hashed, ""]

    # ---- STAGE 6: report ----------------------------------------------------
    with open(os.path.join(findings, "RE-REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    # ---- STAGE 7: final zip -------------------------------------------------
    if "--skip-zip" in flags:
        log("[STAGE 7] skipped (--skip-zip)")
    else:
        log("[STAGE 7] packing final zip ...")
        zip_path = os.path.join(out_base, "%s-FULL-RE.zip" % base_name)
        lvl = 0 if "--store" in flags else 6
        n_zipped = zip_tree(work, zip_path, compresslevel=lvl)
        zsize = os.path.getsize(zip_path)
        log("    %s -> %s (%s, %d files)" % (base_name, os.path.basename(zip_path), human(zsize), n_zipped))
        if "--split" in flags:
            log("    splitting into 45MB parts ...")
            np = split_file(zip_path, 45)
            log("    %d parts + JOIN instructions written" % np)

    dt = time.time() - t0
    log("")
    log("=" * 64)
    log("DONE in %.0fs. Output folder:" % dt)
    log("  %s" % work)
    if not ("--skip-zip" in flags):
        log("  %s" % zip_path)
    log("=" * 64)


if __name__ == "__main__":
    main()
