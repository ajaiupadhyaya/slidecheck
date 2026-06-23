import math
from pptx_a11y.color import relative_luminance, contrast_ratio, suggest_compliant_color


def test_black_on_white_is_21():
    assert math.isclose(contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, rel_tol=1e-3)


def test_same_color_is_1():
    assert math.isclose(contrast_ratio((120, 120, 120), (120, 120, 120)), 1.0, rel_tol=1e-3)


def test_luminance_white_is_1():
    assert math.isclose(relative_luminance((255, 255, 255)), 1.0, rel_tol=1e-3)


def test_suggestion_meets_target_against_white():
    fg = suggest_compliant_color((150, 150, 150), (255, 255, 255), target=4.5)
    assert contrast_ratio(fg, (255, 255, 255)) >= 4.5
