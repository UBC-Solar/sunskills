---
name: local-debug
description: Debug embedded firmware on the local bench - read the user's debugger screenshots, watch live variables over J-Link while the user debugs in VS Code, or run an own GDB session (flash, breakpoints, watchpoints, variable reads). Use when the user says "check the ss", "look through gdb", "watch these variables", "flash the board", or asks to debug hardware behaviour on the STM32 boards.
---

# Local embedded debugging

Bench setup (verify with the commands in "Preflight" - don't assume):

| Item | Value |
|---|---|
| Probe | SEGGER J-Link PLUS (USB `1366:0101`) |
| Target | STM32F103RC (Cortex-M3), SWD, 4000 kHz |
| Tools | `JLinkExe`, `JLinkGDBServer` (`/usr/bin`), `arm-none-eabi-gdb` (STM32Cube bundle, on PATH), `arm-none-eabi-nm` |
| Build | `cmake --build build/Debug` inside `firmware_v4/firmware/components/<board>/` |
| ELF | `firmware_v4/firmware/components/<board>/build/Debug/<board>.elf` |
| VS Code | `.vscode/launch.json` "J-Link + SWO" runs `JLinkGDBServer -singlerun ... -port 50000` |

## Preflight (always)

```bash
lsusb | grep -iE "1366|segger|0483|st-?link"          # probe attached?
pgrep -a -f "JLinkGDBServer|st-util|openocd"          # does someone already own the probe?
ls -l --time-style=+%H:%M:%S build/Debug/*.elf        # is the ELF newer than the source edit?
```

- If `JLinkGDBServer ... -port 50000` is running, **the user is debugging in VS Code**. Use Mode 1
  (read-only). Do not start a second GDB server, and do not halt, reset or flash without asking.
- Symbol addresses come from the ELF. If the ELF is newer than what is flashed, addresses may not
  match the running image - confirm with the user which build is on the board.

## Mode 0 - Screenshots

- Location: `~/Pictures/Screenshots/`. "Most recent ss" = newest by mtime:
  `ls -t ~/Pictures/Screenshots | head`.
- The user often takes a burst ("last couple of ss"): list with times
  (`ls -lt --time-style=+%H:%M:%S`), then Read every image in the burst in parallel.
- If the newest file is unrelated (calendar, dashboard), say so and use the relevant one; don't
  describe unrelated personal content.
- Cortex Live Watch shows arrays as `index: value 'char'` - decode byte runs into ASCII/UBX/etc.
  before drawing conclusions, and note which values the screenshot cuts off.
- If nothing new appeared, check `~/Pictures`, `~/Desktop`, `~/Downloads` for newer images and
  ask the user to re-take it rather than guessing.
- Prefer Mode 1 over asking for more screenshots once the probe is available.

## Mode 1 - Watch variables while the user debugs (read-only, non-intrusive)

J-Link allows a second host connection. `JLinkExe` memory reads go through the debug port while
the core keeps running - no halt, no reset, no interference with the VS Code session.

Helper script (resolves symbols from the ELF, samples, decodes to a table):

```bash
python3 <this skill's base directory>/scripts/jlink_watch.py \
    --elf build/Debug/tel.elf --pattern '^gps_' \
    --samples 10 --interval 10 --signed gps_lat_e7,gps_lon_e7
```

- `--pattern` is a regex on symbol names; only globals/statics (`.bss`/`.data`) can be read.
  Locals can't - make the value a `volatile` global if it must be watched.
- Values print as little-endian unsigned; list signed ones with `--signed`. Arrays/structs longer
  than 4 bytes print as hex + ASCII.
- One-off manual read: get the address with `arm-none-eabi-nm -S <elf> | grep <name>`, then
  `printf 'mem8 0xADDR 0xLEN\nexit\n' > cmd.jlink` and
  `JLinkExe -device STM32F103RC -if SWD -speed 4000 -autoconnect 1 -NoGui 1 -CommandFile cmd.jlink`.
- The line "J-Link Commander will now exit on Error" is the `-ExitOnError` banner, not an error.
- Report trends (a table across samples), not a single snapshot, when diagnosing something that
  should change over time (fix acquisition, counters, state machines).

## Mode 2 - Own GDB session (flash, breakpoints, watchpoints)

Only when no other GDB server owns the probe, and **ask before flashing, resetting or halting** -
it interrupts whatever the board is doing (FreeRTOS timing, I2C transfers, CAN traffic).

1. Build: `cmake --build build/Debug`.
2. Start the server with Bash `run_in_background: true` (port 2331, avoid VS Code's 50000):
   ```bash
   JLinkGDBServer -singlerun -nogui -if swd -device STM32F103RC -speed 4000 -port 2331
   ```
3. Drive GDB in batch mode, always wrapped in `timeout` so a breakpoint that never hits can't hang:
   ```bash
   timeout 60 arm-none-eabi-gdb -q -batch build/Debug/tel.elf \
     -ex "target remote :2331" \
     -ex "monitor reset" -ex "monitor halt" \
     -ex "load" \
     -ex "break TasksGPS" \
     -ex "continue" \
     -ex "info locals" -ex "print gps_ready" -ex "bt" \
     -ex "monitor go" -ex "detach"
   ```
   Drop `load` to debug the image already on the board without reflashing.

Useful commands:

| Goal | GDB |
|---|---|
| Flash the ELF | `load` (after `monitor reset` + `monitor halt`) |
| Reset and run | `monitor reset` then `monitor go` |
| Break at function / line | `break TasksGPS`, `break tasks.c:280`, `tbreak main` (one-shot) |
| Conditional break | `break tasks.c:150 if gps_fix_ok == 1` |
| Log at a line without stopping for long | `dprintf tasks.c:150,"fix=%d sv=%d\n",gps_fix_type,gps_num_sv` then `continue` |
| Stop when a variable changes | `watch gps_fix_ok` (hardware watchpoint; Cortex-M3 has 4) |
| Read variables | `print var`, `print/x var`, `print arr[0]@16`, `x/32xb &buf`, `info locals`, `bt` |
| Peripheral registers | `x/wx 0x40010800` (e.g. GPIOA->CRL on F1), `print/x *(uint32_t*)0x4001080C` |
| Resume and detach | `monitor go`, `detach` |

Notes:
- All-stop GDB can't read memory while the core runs; for live values use Mode 1, or
  `monitor halt` -> read -> `monitor go`.
- Cortex-M3 has 6 hardware breakpoints (FPB); J-Link PLUS adds unlimited flash breakpoints.
- Halting stops FreeRTOS and freezes peripherals mid-transfer (I2C slaves can hold SDA low
  afterwards). Prefer dprintf/watchpoints or Mode 1 when timing matters.
- Stop the background server when done (or let `-singlerun` exit on detach) so VS Code can
  reconnect.

## Reporting

- Quote the raw values (table), then the interpretation, then the next check.
- State what was read live vs. inferred, and whether anything was flashed, reset or halted.
