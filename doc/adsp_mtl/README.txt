========================================================================
= Host Setup

Start with a Zephyr-capable build host on the Intel network (VPN is
fine as long as it's up).

By convention, these instructions group all shared files between the
container and host in a single directory.  Per my usage, it is $HOME/z
on the host, and mounted as /z in the container.  Clone this project
into it (e.g. ~/z/zephyr-ace).

  mkdir ~/z
  cd ~/z
  git clone https://github.com/intel-sandbox/os.rtos.zephyr.zephyr-ace zephyr-ace

The Zephyr tree is best cloned via west.  Note that there are no west
modules required for this build, so no "west update" is needed:

   west init -m https://github.com/intel-innersource/os.rtos.zephyr.zephyr --mr topic/ace-new

Note: these instructions are written to the "topic/ace-new" branch.
This will very soon be merged into the main branch of the repository.

========================================================================
= Docker Container

The audio team maintains a docker image sufficient to build and run
all needed ACE simulator and firmware tools, including Zephyr.  Pull
it with:

    sudo docker pull ger-registry.caas.intel.com/ace-devel/std_sim_mtl

The first clone is slow (coming cross-continent over the IT network).
You'll want to re-pull this regularly as it seems they like to update
it, but that only requires deltas and not the base OS image.

Run it with:

   sudo docker run --name ace_sim -d -i -t \
      --mount type=bind,source=$HOME/z,target=/z \
      ger-registry.caas.intel.com/ace-devel/std_sim_mtl

Open shells in the container with (instead of /bin/bash, you can just
run tools directly from the host too):

   sudo docker exec -it ace_sim /bin/bash

Note that this runs the shell as root.  The image inexplicably lacks
an account with uid=1000 to use for building (i.e. one that matches
the default host user account).  Just do everything as root, I guess.

If for any reason you need to start over with a clean container image,
you can delete the ace_sim container with:

   sudo docker stop ace_sim
   sudo docker rm ace_sim

Finally, we need west in the docker container so we can build
Zephyr. (Note the python interpreter on PATH is a custom installed 3.6
variant and not the distro one, but it works fine.)

   pip3 install west

========================================================================
= Build Zephyr

No special instructions are required to build Zephyr using the Zephyr
SDK.  West works like it does for any other platform.  The board name
is "intel_adsp_ace10".

   cd /z/zephyr
   rm -rf build
   west build -b intel_adsp_ace10 samples/hello_world

If you with to use the (frustratingly slow) Cadence toolchain instead
of GCC, a few environment variables are needed to tell Zephyr where
the toolchain is.  These can be derived the ones already set up for
you by the docker environment:

   export ZEPHYR_BASE=/z/zephyr
   export ZEPHYR_TOOLCHAIN_VARIANT=xcc
   export XTENSA_TOOLCHAIN_PATH=$XTENSA_TOOLS_DIR/$XTENSA_TOOLS_VERSION

========================================================================
= Run

Invocation of the simulator itself is somewhat involved, so the
details are now handled by a "zacewrap.py" script.  In the simple
case, just run this with a pointer to the Zephyr binary in its build
directory.  In fact running it where you ran west with no arguments is
sufficient (the default --image argument is
"./build/zephyr/zephyr.elf").  The script will automatically read from
the trace window in the DSP and emit Zephyr console output.

  /z/zephyr-ace/zacewrap.py

Note that startup is slow, taking ~18 seconds on my laptop to reach
Zephyr initialization.  And once running, it seems to be 200-400x
slower than the emulated cores.  Be patient, especially with code that
busy waits (timers will warp ahead as long as all the cores reach
idle).

By default there is much output printed to the screen while it works.
You can use "--verbose" to get even more logging from the simulator,
or "--quiet" to suppress everything but the Zephyr logging.

By default, zacewrap.py is configured to use prebuilt versions of the
ROM, signing key, simulator and rimage.

Check the --help output, arguments exist to specify either a
zephyr.elf location in a build directory (which must contain the *.mod
files, not just zephyr.elf) or a pre-signed zephyr.ri file, you can
specify paths to alternate binary verions, etc...

Finally, note that the wrapper script is written to use the
Ubuntu-provided Python 3.8 in /usr/bin and NOT the half-decade-stale
Anaconda python 3.6 you'll find ahead of it on PATH. Don't try to run
it with "python" on the command line or change the #! line to use
/usr/bin/env.

========================================================================
= GDB access

GDB protocol (the Xtensa variant thereof -- you must use xt-gdb, an
upstream GNU gdb won't work) debugger access to the cores is provided
by the simulator.  At boot, you will see messages emitted that look
like (these can be hard to find in the scrollback, I apologize):

  Core 0 active:(start with "(xt-gdb) target remote :20000")
  Core 1 active:(start with "(xt-gdb) target remote :20001")
  Core 2 active:(start with "(xt-gdb) target remote :20002")

Note that each core is separately managed.  There is no gdb
"threading" support provided, so it's not possible to e.g. trap a
breakpoint on any core, etc...

Simply choose the core you want (almost certainly 0, debugging SMP
code this way is extremely difficult) and connect to it in a different
shell on the container:

   xt-gdb build/zepyr/zephyr.elf
   (xt-gdb) target remote :20000

Note that the core will already have started, so you will see it
stopped in an arbitrary state, likely in the idle thread.  This
probably isn't what you want, so zacewrap.py provides a
-d/--start-halted option that suppresses the automatic start of the
DSP cores.

Now when gdb connects, the emulated core 0 is halted at the hardware
reset address 0x1ff80000.  You can start the simulator with a
"continue" command, set breakpoints first, etc...

Note that the ROM addresses are part of the ROM binary and not Zephyr,
so the symbol table for early boot will not be available in the
debugger.  As long as the ROM does its job and hands off to Zephyr,
you will be in a safe environment with symbols after a few dozen
instructions.  If you do need to debug the ROM, you can specify it's
ELF file on the command line instead, or use the gdb "file" command to
change the symbol table.

========================================================================
= Run without Docker

If you are using the prebuilt tooling, in fact the Docker environment
is not needed except as a bootstrap process.  What you do need is a
reasonably compatible Linux environment (the Docker image is Ubuntu
20.04) and a copy of the Cadence SDK files which you can find in
/root/xtensa in the image.  Note that you must have the exact version
against which the prebuilt simulator was compiled.

Getting those files out of the image is left as an excercise for the
reader (I just made a tarball).  It's about 10G, so it's a fairly
large copy even on the local disk.  It might be possible to link
directly into the /var/lib/docker tree, but I don't know enough Docker
to say for sure.

But once you have them installed somewhere you can set the
XTENSA_TOOLS_DIR and XTENSA_BUILDS_DIR environment variables to point
to them (for example in ~/xtensa) and the dsp_fw_sim wrapper script
will automatically detect and use them.

    export XTENSA_TOOLS_DIR=$HOME/xtensa/XtDevTools/install/tools
    export XTENSA_BUILDS_DIR=$HOME/xtensa/XtDevTools/install/builds

========================================================================
= Building Rimage

The included binary should be good enough, but if you need to track
upstream changes, the SOF rimage tool is available from public github.
Build it in your host environment, not the docker:

   git clone https://github.com/thesofproject/rimage
   cd rimage
   git submodule init
   git submodule update
   cmake .
   make
   cp ./rimage /z/zephyr-ace

If you do need to make changes to rimage, please make sure to tell
Andy so the prebuilt binary gets updated!

========================================================================
= Building the simulator

The DSP simulator itself can be built from scratch in the container.
The source code from the audio team ("topic/ace" branch) is on the
internal gitlab:

   git clone -b topic/ace https://gitlab.devtools.intel.com/audio_tools/std_sim.git

The tool is itself a C++ program linked against libraries in the
Xtensa SDK.  It's a straightforward build in the container:

  cd /z/std_sim
  source ./scripts/linux/mtl_config.sh
  ./scripts/linux/build_mtl_sim.sh

Likewise, if you do need to make changes to the simulator, please make
sure to tell Andy so the prebuilt binary gets updated!

And for anyone (including Andy) interested in updating the prebuilt:
There are three files to copy (dsp_fw_sim, libgna.so.2 and
intel_dsp/intel_dsp.so -- yes, the extra directory in the path
matters, that's how it's linked).  And note that C++ debug info is
extremely large.  Remember to strip the binaries before committing!

========================================================================
= Building the ROM image

This is the boot ROM for the device, built from audio team code that
we don't touch.  The source code is on a audio team git server in
Europe, which requires the "cAVS_FW_ro" permission in AGS to access.

   git clone -b ace git@repos.igk.intel.com:cavs_fw

The build itself is, like the simulator, trivial to do with a single
script in the container:

   cd /z/cavs_fw/builder
   ./build.sh -e buildenvs/buildenv_mtl.sh \
       -e buildenvs/buildenv_sim_rom.sh \
       -e buildenvs/buildenv_local.sh
   cp /z/cavs_fw/artifacts/FW/bin/mtl/rom/sim/dsp_rom_mtl_sim.hex /z/zephyr-ace

And again: if you do need to make changes to the ROM, please make sure
to tell Andy so the prebuilt binary gets updated!
