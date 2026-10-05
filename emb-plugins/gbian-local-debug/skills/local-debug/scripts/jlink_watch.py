#!/usr/bin/env python3
"""Sample global variables from a running target over J-Link (read-only).

Resolves addresses from the ELF with arm-none-eabi-nm, reads them with JLinkExe
mem8 (no halt/reset/flash - safe alongside a VS Code debug session), and prints
one row per sample.

Example:
    jlink_watch.py --elf build/Debug/tel.elf --pattern '^gps_' --samples 10 --interval 10
"""
import argparse
import re
import subprocess
import sys
import tempfile


def read_symbols(elf, pattern):
    out = subprocess.run(["arm-none-eabi-nm", "-S", elf], capture_output=True, text=True, check=True).stdout
    rx = re.compile(pattern)
    syms = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[2] not in "bBdD":
            continue
        addr, size, _, name = parts
        if rx.search(name):
            syms.append((int(addr, 16), int(size, 16), name))
    return sorted(syms)


def spans(syms, gap=64):
    """Merge nearby symbols into contiguous read ranges."""
    out = []
    for addr, size, _ in syms:
        if out and addr <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], addr + size)
        else:
            out.append([addr, addr + size])
    return [(lo, hi - lo) for lo, hi in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", required=True)
    ap.add_argument("--pattern", default=".", help="regex on symbol names")
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between samples")
    ap.add_argument("--signed", default="", help="comma-separated names to print as signed")
    ap.add_argument("--device", default="STM32F103RC")
    ap.add_argument("--speed", default="4000")
    args = ap.parse_args()

    syms = read_symbols(args.elf, args.pattern)
    if not syms:
        sys.exit("no matching .bss/.data symbols")
    ranges = spans(syms)
    signed = set(filter(None, args.signed.split(",")))

    cmds = []
    for i in range(args.samples):
        cmds += [f"mem8 0x{lo:08X} 0x{ln:X}" for lo, ln in ranges]
        if i < args.samples - 1:
            cmds.append(f"sleep {int(args.interval * 1000)}")
    cmds.append("exit")

    with tempfile.NamedTemporaryFile("w", suffix=".jlink", delete=False) as f:
        f.write("\n".join(cmds) + "\n")
        cmdfile = f.name

    timeout = 30 + args.samples * (args.interval + 2)
    res = subprocess.run(
        ["JLinkExe", "-device", args.device, "-if", "SWD", "-speed", args.speed,
         "-autoconnect", "1", "-NoGui", "1", "-ExitOnError", "1", "-CommandFile", cmdfile],
        capture_output=True, text=True, timeout=timeout)

    # Each mem8 line: "AAAAAAAA = BB BB ...". A repeated start address begins a new sample.
    samples, cur, seen = [], {}, set()
    for line in res.stdout.splitlines():
        m = re.match(r"^([0-9A-F]{8}) = ((?:[0-9A-F]{2} ?)+)$", line.strip())
        if not m:
            continue
        base = int(m.group(1), 16)
        if base in seen:
            samples.append(cur)
            cur, seen = {}, set()
        seen.add(base)
        for k, b in enumerate(m.group(2).split()):
            cur[base + k] = int(b, 16)
    if cur:
        samples.append(cur)
    if not samples:
        sys.exit("no data read - is the probe connected?\n" + res.stdout[-2000:])

    def fmt(mem, addr, size, name):
        raw = bytes(mem.get(addr + k, 0) for k in range(size))
        if size in (1, 2, 4):
            return str(int.from_bytes(raw, "little", signed=name in signed))
        text = "".join(chr(c) if 32 <= c < 127 else "." for c in raw[:16])
        return raw[:16].hex(" ") + ("..." if size > 16 else "") + f" |{text}|"

    scalars = [s for s in syms if s[1] in (1, 2, 4)]
    arrays = [s for s in syms if s[1] not in (1, 2, 4)]
    names = [n.split(".")[0] for _, _, n in scalars]
    width = max([len(n) for n in names] + [8])

    print(f"{'sample':>6}  " + "  ".join(f"{n:>{width}}" for n in names))
    for i, mem in enumerate(samples):
        print(f"{i * args.interval:>6.0f}  " + "  ".join(f"{fmt(mem, a, s, n):>{width}}" for a, s, n in scalars))
    for a, s, n in arrays:
        print(f"{n} [{s} B] (last sample): {fmt(samples[-1], a, s, n)}")


if __name__ == "__main__":
    main()
