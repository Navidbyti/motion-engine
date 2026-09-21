"""Declared feature surface of the M2 raster preview backend."""

PREVIEW_PARAMS = {
    "text": {"color", "fontSize", "wrap"},
    "shape": {"color", "shape", "gradientEnd", "gradientDirection"},
    "image": {"fit"},
    "video": {"fit", "sourceStartFrame"},
    "audio": {"gainDb", "sourceStartFrame", "fadeInFrames", "fadeOutFrames", "role"},
    "counter": {"startValue", "endValue", "decimals", "prefix", "suffix", "color", "fontSize", "fontFamily", "digitPolicy", "align"},
    "chart.bar": {"categoryField", "minimum", "maximum", "color", "baselineColor", "barWidthFraction", "labelFontFamily", "tickCount", "showValues"},
    "chart.line": {"categoryField", "minimum", "maximum", "color", "baselineColor", "labelFontFamily", "tickCount", "showValues"},
}
PREVIEW_KINDS = set(PREVIEW_PARAMS)
PREVIEW_ANIMATIONS = {"opacity", "reveal", "scale", "value", "x", "y"}
PREVIEW_ANIMATIONS_BY_KIND = {
    "text": {"opacity", "x", "y"},
    "shape": {"opacity", "x", "y"},
    "image": {"opacity", "scale", "x", "y"},
    "video": {"opacity", "scale", "x", "y"},
    "audio": set(),
    "counter": {"value", "opacity", "x", "y"},
    "chart.bar": {"reveal"},
    "chart.line": {"reveal"},
}
PREVIEW_EASING = {"linear", "ease_out", "ease_in", "ease_in_out", "hold"}
