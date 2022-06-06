# SPDX-License-Identifier: Apache-2.0

board_set_flasher_ifnset(misc-flasher)
board_runner_args(misc-flasher "${BOARD_DIR}/support/zacewrap.py")
board_finalize_runner_args(misc-flasher)
board_set_rimage_target(mtl)
