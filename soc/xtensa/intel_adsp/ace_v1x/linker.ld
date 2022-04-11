/* Copyright (c) 2022 Intel Corporation
 * SPDX-License-Identifier: Apache-2.0
 */
#include <cavs-link.ld>

MEMORY
{
    LINKER_DT_RESERVED_MEM_REGIONS()
}

SECTIONS
{
    LINKER_DT_RESERVED_MEM_SECTIONS()
}
