/*
 * Copyright (c) 2022 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <device.h>
#include <xtensa/xtruntime.h>
#include <irq_nextlevel.h>
#include <xtensa/hal.h>
#include <init.h>


#include <ace_v1x-regs.h>
#include "soc.h"

extern void soc_mp_init(void);

static __imr void power_init_mtl(void)
{
	/* Disable idle power gating */
	MTL_PWRBOOT.bootctl[0].bctl |=
		MTL_PWRBOOT_BCTL_WAITIPCG | MTL_PWRBOOT_BCTL_WAITIPPG;
}

static __imr int soc_init(const struct device *dev)
{
	power_init_mtl();
	z_soc_irq_init();

#if CONFIG_MP_NUM_CPUS > 1
	soc_mp_init();
#endif

	return 0;
}

SYS_INIT(soc_init, PRE_KERNEL_1, 99);
