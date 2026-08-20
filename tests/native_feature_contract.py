# SPDX-FileCopyrightText: 2026 MLC Player contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Native feature smoke ebeveyni ve child'i icin ortak sabit sozlesme."""

OPT_IN_VARIABLE = "MLC_NATIVE_FEATURE_ACCEPTANCE"
OPT_IN_VALUE = "1"
MEDIA_VARIABLE = "MLC_NATIVE_TEST_VIDEO"

REQUIRED_CHECKS = (
    "maximize_toggle",
    "pip_from_maximized_is_compact",
    "pip_restores_maximized",
    "pip_from_fullscreen_is_compact",
    "bottom_left_cursor",
    "bottom_right_cursor",
    "transparency_adjustable",
    "picture_in_picture",
    "picture_in_picture_initial_mouse_exit",
    "picture_in_picture_drag_from_video",
    "picture_in_picture_resizable",
    "picture_in_picture_exit_hit_target",
    "picture_in_picture_mouse_exit",
    "timeline_immediate",
    "duration_arrived",
    "natural_end_rewinds_and_pauses",
    "stop_non_blocking",
)

OPTIONAL_CHECKS = ("picture_in_picture_screenshot",)
