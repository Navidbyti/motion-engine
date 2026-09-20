"""Declared feature surface of the M2 raster preview backend."""

PREVIEW_PARAMS = {
    "text": {"color", "fontSize", "wrap"},
    "shape": {"color", "shape"},
    "image": {"fit"},
    "video": {"fit", "sourceStartFrame"},
    "audio": {"gainDb"},
    "chart.bar": {"categoryField", "minimum", "maximum", "color", "baselineColor", "barWidthFraction", "labelFontFamily"},
    "chart.line": {"minimum", "maximum", "color", "baselineColor", "labelFontFamily"},
}
PREVIEW_KINDS = set(PREVIEW_PARAMS)
PREVIEW_ANIMATIONS = {"opacity", "reveal", "scale", "x", "y"}
PREVIEW_ANIMATIONS_BY_KIND = {
    "text": {"opacity", "x", "y"},
    "shape": {"opacity", "x", "y"},
    "image": {"opacity", "scale", "x", "y"},
    "video": {"opacity", "scale", "x", "y"},
    "audio": set(),
    "chart.bar": {"reveal"},
    "chart.line": {"reveal"},
}
PREVIEW_EASING = {"linear", "ease_out", "ease_in", "ease_in_out", "hold"}
