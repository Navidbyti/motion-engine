"""Declared feature surface of the M2 raster preview backend."""

PREVIEW_PARAMS = {
    "text": {"color", "fontSize"},
    "shape": {"color", "shape"},
    "chart.bar": {"categoryField", "minimum", "maximum", "color", "baselineColor", "barWidthFraction", "labelFontFamily"},
    "chart.line": {"minimum", "maximum", "color", "baselineColor", "labelFontFamily"},
}
PREVIEW_KINDS = set(PREVIEW_PARAMS)
PREVIEW_ANIMATIONS = {"opacity", "reveal"}
PREVIEW_ANIMATIONS_BY_KIND = {
    "text": {"opacity"},
    "shape": {"opacity"},
    "chart.bar": {"reveal"},
    "chart.line": {"reveal"},
}
PREVIEW_EASING = {"linear", "ease_out", "ease_in", "ease_in_out", "hold"}
