#!/usr/bin/python3
import asyncio
import argparse
import tempfile
import re
import sys
import os.path
import subprocess
import struct
import types

PORT = 40008 # Any port will work, this is conventional

# Simulator doesn't implement the window mapping in PCI space, so read
# directly out of HP-SRAM instead.
#
#TRACE_WIN_ADDR = 0x20000000 + (0x80000 + (3 * 0x20000)) # Window 3 offset in BAR2
TRACE_WIN_ADDR = 0x3002a000 # == HP_SRAM_WIN3_BASE (w/ offset)

state = types.SimpleNamespace()
state.gdb = "xt-gdb"
state.mem_reads = {}
state.mem_read_seq = 0

# Some verbose output it just too verbose.  The sim wants to log four
# lines for every scheduler IPI! (The author's assumption was that
# these would be rare, I guess. Zephyr throws them around like popcorn
# at a bad movie).
suppress = (re.compile(r".*DSP\d -> DSP\d IDC msg:.*"),
            re.compile(r".*IDC DONE INTERRUPT ON CORE.*"))

def log(msg):
    if args.verbose:
        print("WRAPPER: " + msg)

async def readword(rstream):
    return struct.unpack("<I", await rstream.readexactly(4))[0]

async def sim_cmd(id, *data):
    words = (id, 4 * len(data)) + data
    buf = b''.join(struct.pack("<I", x) for x in words)
    state.sim_ctrl.write(buf)
    await state.sim_ctrl.drain()

# Main loop for incoming commands from simulator, protocol is a stream
# of dwords: [id, data_len, data...].  Note that the length is passed
# in bytes, even though all I/O is in units of 4.
async def sim_connection(reader, writer):
    state.sim_ctrl = writer
    while True:
        (id, len) = (await readword(reader), await readword(reader) >> 2)
        data = [ await readword(reader) for i in range(len)]
        if id == 0 or id == 3: # HEARTBEAT, TICK
            pass
        elif id == 1: # HELLO
            log("HELLO received")
            state.hello_event.set()
        elif id == 2: # GOODBYE
            log("GOODBYE command received, exiting")
            sys.exit(0)
        elif id == 0x402: # MEM_READ_RESP
            seq = data[0]
            state.mem_reads[seq].append(data[1:])
            state.mem_reads[seq][0].set()
        else:
            print(f"Unrecognized protocol command 0x{id:x} [",
                  " ".join(f"0x{x:x}" for x in data), "]")
        # Awful: the simulator has a synchronous loop!
        # (c.f. intel_dsp/host_module/comm.cpp) It will get stuck in a
        # read() call on the socket if it doesn't get regular input,
        # so we have to keep it constantly churning on noop heartbeats
        # to keep it moving. Ugh.
        await sim_cmd(0) # HEARTBEAT

async def write_mem(addr, value):
    await sim_cmd(0x403, addr, 4, value) # MEM_WRITE_REQ of 4 bytes

async def read_mem(addr, nwords):
    state.mem_read_seq += 1
    rec = [asyncio.Event(), state.mem_read_seq] # Handler will append result
    state.mem_reads[state.mem_read_seq] = rec
    await sim_cmd(0x401, addr, 4 * nwords, state.mem_read_seq) # MEM_READ_REQ
    await rec[0].wait()
    del state.mem_reads[rec[1]]
    return rec[2]

# Protocol only does LE dwords, this pads and converts to bytes
async def read_mem_bytes(addr, n):
    prepad = addr & 3
    nwords = (((n + prepad) + 3) & ~3) >> 2
    words = await read_mem(addr - prepad, nwords)
    bs = b''.join(struct.pack("<I", x) for x in words)
    return bs[prepad:prepad + n]

# Returns tuple of (new_seq, new_data_bytes)
#
# Note: the "proper" algorithm here (c.f. sys_winstream_read())
# requires a loop and a re-check of start/end/seq at the end to make
# sure the reader didn't race against an very large update on the
# other side that affected data it had read.  Unfortunately that
# doesn't work well on the simulator because the socket protocol for
# reads is VERY SLOW and the simulator can trivially defeat it,
# leading to frozen output until the sim stops talking for a while.
#
async def winstream_read(addr, last_seq):
    (wlen, start, end, seq) = await read_mem(addr, 4)
    if seq == last_seq or start == end:
        return (seq, b'')
    behind = seq - last_seq
    if behind > ((end - start) % wlen):
        return (seq, b'')
    copy = (end - behind) % wlen
    suffix = min(behind, wlen - copy)
    result = await read_mem_bytes(addr + 16 + copy, suffix)
    if suffix < behind:
        result += await read_mem_bytes(addr + 16, behind - suffix)
    (start1, end1, seq1) = await read_mem(addr + 4, 3)
    return (seq, result)

# Reads/prints simulator output (used for both stdout and stderr),
# watches for notification of gdb ports, which aren't reliable (the
# sim will bump the port if it can't open it due to TIME_WAIT or
# whatever)
async def sim_output(stream):
    while True:
        s = (await stream.readline()).decode("utf-8")
        quiet = args.quiet
        for p in suppress:
            if p.match(s):
                quiet = True
                break
        if not quiet:
            sys.stdout.write(s)
            sys.stdout.flush()
        m = re.match(r'PREBUILT: xt-bin-path: (.*)', s.rstrip())
        if m:
            state.gdb = os.path.join(m.group(1), "xt-gdb")
        m = re.match(r'NOTE\s+core(\d+)\s.*Debug info:.*port=(\d+)', s)
        if m:
            # Launch a background gdb to start the core
            port = int(m.group(2))
            if (not args.quiet) or args.start_halted:
                print(f"Core {m.group(1)} active:"
                      f"(start with \"(xt-gdb) target remote :{port}\")")
            if not args.start_halted:
                log(f"Launching GDB to start core {m.group(1)}")
                await asyncio.create_subprocess_exec(
                    state.gdb, "-ex", f"target remote :{port}", "-ex", "continue",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE)

def write_sim_cfg(signed_image):
    params = os.path.dirname(args.sim)
    state.cfgtmp = tempfile.NamedTemporaryFile()
    l = [f"[binaries]",
         f"bin_rom         = {args.rom}",
         f"bin_fw          = {signed_image}",
         f"[parameters]",
         f"wall_clock_inc = 240",
         f"tick_period    = 10",
         f"verb_level     = {args.verb}", # 0-4 = off,crit,normal,verbose,very_verbose
         f"[fabric_params]",
         f"turbo_hpsram    = true",
         f"turbo_lpsram    = true"]
    for s in l:
        state.cfgtmp.file.write((s + "\n").encode("utf-8"))
    state.cfgtmp.file.flush()
    return state.cfgtmp.name

async def _main(signed_image):
    # Open up a server socket to which the simulator will connect
    state.hello_event = asyncio.Event()
    svr = await asyncio.start_server(sim_connection, port=PORT)

    # Launch the simulator, listening to its output.  Note that it
    # requires that it be run in its own directory.  Either
    # --xtsc.turbo or --turbo (I don't understand the distinction)
    # must be specified otherwise the sim won't set up HP-SRAM.  And
    # --xxdebug=N is needed because otherwise no gdb socket will be
    # created for core N, leaving it halted (I haven't found a way to
    # Just Start the Cores, the gdb code is in the xtensa libraries
    # and we don't have source or docs)
    cfg = write_sim_cfg(signed_image)
    cmd = (f"cd '{os.path.dirname(args.sim)}'; " +
           " ".join((args.sim, "--platform=mtl",
                     f"--config={cfg}",
                     f"--comm_port={PORT}",
                     "--xtsc.turbo=true",
                     "--xxdebug=0",
                     "--xxdebug=1",
                     "--xxdebug=2"
                     )))
    sim = await asyncio.create_subprocess_shell(cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    asyncio.create_task(sim_output(sim.stdout))
    asyncio.create_task(sim_output(sim.stderr))

    # Wait for the HELLO message to arrive from a connected simulator
    log("Waiting for HELLO message")
    await state.hello_event.wait()

    # Now set up the hardware to enable the core to start:
    log("Writing reset/startup registers")
    await write_mem(0x00000008, 1)       # HDA GCTL  (reset audio device)
    await write_mem(0x20073228, 3)       # HfIPC0CTL (enable IPC)
    await write_mem(0x20001000, 1 << 16) # HfDSSCS   (power-on DSP)

    # And finally loop, watching the hardware logging window for data
    seq = 0
    while True:
        (seq, log_output) = await winstream_read(TRACE_WIN_ADDR, seq)
        if log_output and not args.no_window_trace:
            sys.stdout.write(log_output.decode("utf-8"))
            sys.stdout.flush()
        await asyncio.sleep(0.2)



def main():
    global args

    zacedir = os.path.dirname(__file__) + "/"
    ap = argparse.ArgumentParser(description="Run ACE 1.x Simulator")
    ap.add_argument("-s", "--sim", default=os.path.join(zacedir, "dsp_fw_sim"),
		    help="Path to built simulator binary")
    ap.add_argument("-m", "--rimage", default=os.path.join(zacedir, "rimage"),
		    help="Path to built rimage binary")
    ap.add_argument("-i", "--image", default="./build/zephyr/zephyr.elf",
		    help="Path to zephyr.elf (in its build directory!) or zephyr.ri")
    ap.add_argument("-r", "--rom", default=os.path.join(zacedir, "dsp_rom_mtl_sim.hex"),
		    help="Path to built ROM binary")
    ap.add_argument("-t", "--toml", default=os.path.join(zacedir, "ace10.toml"),
		    help="Rimage TOML configuration file")
    ap.add_argument("-k", "--key", default=os.path.join(zacedir, "dummy-key.pem"),
		    help="Path to PEM key for rimage signing")
    ap.add_argument("-v", "--verbose", action="store_true",
		    help="Display extra simulator output")
    ap.add_argument("-q", "--quiet", action="store_true",
		    help="Suppress all simulator logging, show only Zephyr output")
    ap.add_argument("-d", "--start-halted", action="store_true",
		    help="Don't start cores automatically, use external gdb")
    ap.add_argument("-w", "--no-window-trace", action="store_true",
		    help="Don't read trace output from shared memory window")
    ap.add_argument("build_dir", nargs="?", help="build file path passing from west")

    args = ap.parse_args()

    # When zacewrap.py run by west flash, the argv[1] will be the build directory path.
    # In this case, we use it for getting where the zephyr.elf is.
    if args.build_dir:
        args.image = os.path.join(args.build_dir, "zephyr", "zephyr.elf")
    else:
        args.image = os.path.join(os.getenv('PWD'), args.image)

    args.verb = 1
    if args.quiet:
        args.verb = 0
    if args.verbose:
        args.verb = 3

    image_dir = os.path.dirname(args.image)
    signed_image = os.path.join(image_dir, "zephyr.ri")

    # Sign image if needed
    with open(args.image, "rb") as f:
        if not os.path.exists(signed_image) and f.read(4) == b'\x7fELF':
            log("Signing image with rimage...")
            boot_mod = os.path.join(image_dir, "boot.mod")
            main_mod = os.path.join(image_dir, "main.mod")
            cmd = (args.rimage, "-k", args.key, "-o", signed_image, "-c", args.toml,
                    "-i", "3", boot_mod, main_mod)
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if cp.returncode != 0 or args.verbose:
                print(" ".join(cmd))
                print(cp.stdout.decode("utf-8"))
                if cp.returncode != 0:
                    sys.exit(0)

    asyncio.run(_main(signed_image))

if __name__ == "__main__":
    try:
        main()
    finally:
        if (os.name != "nt") and os.isatty(1):
            # (OS is not Windows) and (stdout is interactive)
            os.system("stty sane")
