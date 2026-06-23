def _channel(c: int) -> float:
    s = c / 255.0
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def suggest_compliant_color(fg, bg, target: float) -> tuple[int, int, int]:
    """Move fg toward black or white (whichever helps) until target is met."""
    toward = (0, 0, 0) if relative_luminance(bg) > 0.5 else (255, 255, 255)
    best = fg
    for step in range(1, 21):
        t = step / 20.0
        cand = tuple(round(fg[i] + (toward[i] - fg[i]) * t) for i in range(3))
        if contrast_ratio(cand, bg) >= target:
            return cand
        best = cand
    return best
