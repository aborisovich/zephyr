/* Copyright (c) 2022 Intel Corporation
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef ZEPHYR_SOC_INTEL_ADSP_IPC_REGS_H
#define ZEPHYR_SOC_INTEL_ADSP_IPC_REGS_H

#include <zephyr/devicetree.h>
#include <stdint.h>

/**
 * @brief IPC registers layout for every Intel ADSP SoC family.
 */
struct intel_adsp_ipc {
#if defined(CONFIG_INTEL_ADSP_CAVS)
#if defined(CONFIG_SOC_SERIES_INTEL_CAVS_V15)
	uint32_t tdr;
	uint32_t tdd;
	uint32_t idr;
	uint32_t idd;
	uint32_t ctl;
	uint32_t ida; /* Fakes for source compatibility; these ...  */
	uint32_t tda; /* ... two registers don't exist in hardware. */
#else /* Remaining CAVS SoCs */
	uint32_t tdr;
	uint32_t tda;
	uint32_t tdd;
	uint32_t unused0;
	uint32_t idr;
	uint32_t ida;
	uint32_t idd;
	uint32_t unused1;
	uint32_t cst;
	uint32_t csr;
	uint32_t ctl;
#endif /* CONFIG_SOC_SERIES_INTEL_CAVS_V15 */
#endif /* CONFIG_INTEL_ADSP_CAVS */

#ifdef CONFIG_SOC_SERIES_INTEL_ACE1X
	uint32_t tdr;
	uint32_t tda;
	uint32_t unused0[2];
	uint32_t idr;
	uint32_t ida;
	uint32_t unused1[2];
	uint32_t cst;
	uint32_t csr;
	uint32_t ctl;
	uint32_t cap;
	uint32_t unused2[52];
	uint32_t tdd;
	uint32_t unused3[31];
	uint32_t idd;
#endif /* CONFIG_SOC_SERIES_INTEL_ACE1X */
};

#define INTEL_ADSP_IPC_BUSY BIT(31)
#define INTEL_ADSP_IPC_DONE BIT(31)

#define INTEL_ADSP_IPC_CTL_TBIE BIT(0)
#define INTEL_ADSP_IPC_CTL_IDIE BIT(1)

/**
 * @brief Retrieve node identifier for Intel ADSP host IPC.
 */
#define INTEL_ADSP_IPC_HOST_DTNODE DT_NODELABEL(intel_adsp_host_ipc)

/** @brief Host IPC device pointer.
 *
 * This macro expands to the registered host IPC device from
 * devicetree (if one exists!). The device will be initialized and
 * ready at system startup.
 */
#define INTEL_ADSP_IPC_HOST_DEV DEVICE_DT_GET(INTEL_ADSP_IPC_HOST_DTNODE)

/**
 * @brief IPC register block.
 *
 * This macro retrieves host IPC register address from devicetree.
 */
#define INTEL_ADSP_IPC_REG_ADDRESS DT_REG_ADDR(INTEL_ADSP_IPC_HOST_DTNODE)

/**
 * @brief Retrieve node identifier for Intel ADSP IDC.
 */
#define INTEL_ADSP_IDC_DTNODE DT_NODELABEL(intel_adsp_idc)

/**
 * @brief IDC register block.
 *
 * This macro retrieves IDC register address from devicetree.
 */
#define INTEL_ADSP_IDC_REG_ADDRESS DT_REG_ADDR(INTEL_ADSP_IDC_DTNODE)

#endif /* ZEPHYR_SOC_INTEL_ADSP_IPC_REGS_H */
