# Intel ACE SoC family CMake file
#
# Copyright (c) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

zephyr_library_sources_ifdef(CONFIG_SOC_SERIES_INTEL_ACE1X
	boot.c
	rimage_modules.c
	power_down.S
	)
