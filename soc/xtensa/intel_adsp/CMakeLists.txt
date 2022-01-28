# Intel CAVS SoC family CMake file
#
# Copyright (c) 2020 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


add_subdirectory(common)
add_subdirectory(ace_v1x)
add_subdirectory(${ZEPHYR_BASE}/soc/${ARCH}/${SOC_FAMILY} soc/family)
zephyr_include_directories(${ZEPHYR_BASE}/soc/${ARCH}/${SOC_FAMILY}/common/include)
