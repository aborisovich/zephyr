/*
 * Copyright (c) 2022 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <device.h>
#include <devicetree.h>
#include <irq_nextlevel.h>
#ifdef CONFIG_DYNAMIC_INTERRUPTS
#include <sw_isr_table.h>
#endif
#include <soc.h>
#include <ace_v1x-regs.h>

/* MTL device interrupts are all packed into a single line on Xtensa's
 * architectural IRQ 4 (see below), run by a Designware interrupt
 * controller with 28 lines instantiated.  They get numbered
 * immediately after the Xtensa interrupt space in the numbering
 * (i.e. interrupts 0-31 are Xtensa IRQs, 32 represents DW input 0,
 * etc...).
 *
 * That IRQ 4 indeed has an interrupt type of "EXTERN_LEVEL" and an
 * interrupt level of 2.  The CPU has a level 1 external interrupt on
 * IRQ 1 and a level 3 on IRQ 6, but nothing seems wired there.  Note
 * that this level 2 ISR is also shared with the CCOUNT timer on IRQ3.
 * This interrupt is a very busy place!
 *
 * But, because there can never be a situation where all interrupts on
 * the Synopsys controller are disabled (such a system would halt
 * forever if it reached idle!), we at least can take advantage to
 * implement a simplified masking architecture.  Xtensa INTENABLE
 * always has the line active, and we do all masking of external
 * interrupts on the single controller.
 *
 * Finally: note that there is an extra layer of masking on MTL.  The
 * MTL_DINT registers provide separately maskable interrupt delivery
 * for each core, and with some devices for different internal
 * interrupt sources.  Responsibility for these mask bits is left with
 * the driver.
 *
 * Thus, the masking architecture picked here is:
 *
 * + Drivers manage MTL_DINT themselves, as there are device-specific
 *   mask indexes that only the driver can interpret.  If
 *   core-asymmetric interrupt routing needs to happen, it happens
 *   here.
 *
 * + The DW layer is en/disabled uniformly across all cores.  This is
 *   the layer toggled by arch_irq_en/disable().
 *
 * + Index 4 in the INTENABLE SR is set at core startup and stays
 *   enabled always.
 */

#define IS_DW(irq) ((irq) >= XCHAL_NUM_INTERRUPTS)

void z_soc_irq_enable(uint32_t irq)
{
	if (IS_DW(irq)) {
		for (int i = 0; i < CONFIG_MP_NUM_CPUS; i++) {
			ACE_INTC[i].inten |= BIT(MTL_IRQ_FROM_ZEPHYR(irq));
		}
	} else {
		z_xtensa_irq_enable(irq);
	}
}

void z_soc_irq_disable(uint32_t irq)
{
	if (IS_DW(irq)) {
		for (int i = 0; i < CONFIG_MP_NUM_CPUS; i++) {
			ACE_INTC[i].inten &= ~BIT(MTL_IRQ_FROM_ZEPHYR(irq));
		}
	} else {
		z_xtensa_irq_disable(irq);
	}
}

int z_soc_irq_is_enabled(unsigned int irq)
{
	if (IS_DW(irq)) {
		return ACE_INTC[0].inten & BIT(MTL_IRQ_FROM_ZEPHYR(irq));
	} else {
		return z_xtensa_irq_is_enabled(irq);
	}
}

#ifdef CONFIG_DYNAMIC_INTERRUPTS
int z_soc_irq_connect_dynamic(unsigned int irq, unsigned int priority,
			      void (*routine)(const void *parameter),
			      const void *parameter, uint32_t flags)
{
	/* Simple architecture means that the Zephyr irq number and
	 * the index into the ISR table are identical.
	 */
	ARG_UNUSED(flags);
	ARG_UNUSED(priority);
	z_isr_install(irq, routine, parameter);
	return irq;
}
#endif

static ALWAYS_INLINE uint32_t processor_id_reg(void)
{
	uint32_t prid;

	__asm__ volatile("rsr %0, PRID" : "=r"(prid));
	return prid;
}

static void dwint_isr(const void *arg)
{
	uint32_t fs = ACE_INTC[processor_id_reg()].finalstatus;

	while (fs) {
		uint32_t bit = find_lsb_set(fs) - 1;
		struct _isr_table_entry *ent = &_sw_isr_table[MTL_IRQ_TO_ZEPHYR(bit)];

		fs &= ~BIT(bit);
		ent->isr(ent->arg);
	}
}

void z_soc_irq_init(void)
{
	IRQ_CONNECT(ACE_INTC_IRQ, 0, dwint_isr, 0, 0);
	z_xtensa_irq_enable(ACE_INTC_IRQ);
}
