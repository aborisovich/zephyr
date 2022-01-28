/* Copyright (c) 2021 Intel Corporation
 * SPDX-License-Identifier: Apache-2.0
 */

/* THIS IS NOT AN XTENSA HEADER!
 *
 * The purpose of this header is to act as a standin for <tie-asm.h>
 * in Zephyr builds.  The MTL hardware instantiates hardware registers
 * that aren't supported by the GCC-based Zephyr SDK compiler.  These
 * definitions then propagate into the HAL source, where it generates
 * incompatible assembly.  Zephyr does not use the HAL, but it does
 * need to build it.  And the relevant code is exclusively in context
 * save/switch utilities which Zephyr does not use.
 *
 * It's a hack, basically.  But it's a relatively clean way to
 * preserve gcc compatibility without modifying the upstream
 * toolchain.
 */

#ifdef __XCC__
#include "tie-asm-mtl.h"
#else
#include "tie-asm-cavs25.h"
#endif
