# -*- coding: utf-8 -*-
"""Deck theme: the app's own visual system, restated at slide scale.

The palette, the type hierarchy and the icon set are lifted directly from
frontend/styles.css and frontend/icons.js so the presentation and the product
look like the same piece of work. Two rules carry over unchanged:

* **No emoji.** Icons are stroked geometry on a 24-unit grid, drawn here with
  PowerPoint primitives, so they inherit the colour of whatever they label
  instead of arriving in some vendor's font.
* **Colour is information.** The six category tones mean the same thing on a
  slide as they do on the home screen; nothing is tinted for decoration.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------- palette
BG        = RGBColor(0xF4, 0xF5, 0xF6)
SURFACE   = RGBColor(0xFF, 0xFF, 0xFF)
SURFACE_2 = RGBColor(0xEE, 0xF0, 0xF1)
INK       = RGBColor(0x16, 0x21, 0x1F)
INK_2     = RGBColor(0x5A, 0x6B, 0x68)
INK_3     = RGBColor(0x8A, 0x99, 0x96)
LINE      = RGBColor(0xE2, 0xE5, 0xE7)

PRIMARY      = RGBColor(0x0A, 0x61, 0x52)
PRIMARY_2    = RGBColor(0x0D, 0x7A, 0x66)
PRIMARY_INK  = RGBColor(0x06, 0x3E, 0x34)
PRIMARY_SOFT = RGBColor(0xE8, 0xF0, 0xEE)
ACCENT       = RGBColor(0xA8, 0x5A, 0x15)
GOLD         = RGBColor(0x8A, 0x6A, 0x12)
DANGER       = RGBColor(0x9E, 0x2B, 0x24)
OK           = RGBColor(0x25, 0x6B, 0x3C)

# The six category tones, same meanings as the home screen.
T_MONEY  = RGBColor(0x0A, 0x61, 0x52)
T_SEND   = RGBColor(0xA8, 0x5A, 0x15)
T_SCHEME = RGBColor(0x1D, 0x4E, 0x7A)
T_LEARN  = RGBColor(0x57, 0x41, 0x92)
T_SCAN   = RGBColor(0x14, 0x64, 0x6E)
T_SAFETY = RGBColor(0x9E, 0x2B, 0x24)

# On the dark title slide the light tokens invert.
ON_DARK   = RGBColor(0xFF, 0xFF, 0xFF)
ON_DARK_2 = RGBColor(0xB9, 0xCE, 0xC8)
ON_DARK_3 = RGBColor(0x7E, 0x9C, 0x94)

FONT = "Segoe UI"

SLIDE_W = Inches(13.3333)
SLIDE_H = Inches(7.5)


def mix(tone, pct, base=SURFACE):
    """color-mix(in srgb, tone pct%, base) -- the same chip tint the tiles use."""
    return RGBColor(*[int(round(t * pct + b * (1 - pct))) for t, b in zip(tone, base)])


# ---------------------------------------------------------------- surfaces
def flatten(shape):
    """Remove PowerPoint's default shape style and effects.

    ``shadow.inherit = False`` writes an empty effect list, but every autoshape
    also carries a <p:style> element pointing at the theme's effect reference,
    and some renderers honour that instead. Deleting the style element is the
    only way to be sure a card is genuinely flat -- and flat matters here,
    because tinted offset shadows are one of the things that made this
    project's first UI look amateur.
    """
    shape.shadow.inherit = False
    style = shape._element.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}style")
    if style is not None:
        shape._element.remove(style)
    return shape


def set_bg(slide, color=BG):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def card(slide, x, y, w, h, fill=SURFACE, outline=LINE, radius=0.06):
    shape = flatten(slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h))
    shape.adjustments[0] = radius
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if outline is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = outline
        shape.line.width = Pt(0.75)
    return shape


def rule(slide, x, y, w, color=LINE, weight=1.0):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x, y, x + w, y)
    ln.line.color.rgb = color
    ln.line.width = Pt(weight)
    return ln


def bar(slide, x, y, w, h, color):
    shape = flatten(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h))
    shape.line.fill.background()
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    return shape


# ------------------------------------------------------------------- text
def text(slide, x, y, w, h, body, size=14, color=INK_2, bold=False,
         align=PP_ALIGN.LEFT, line=1.25, space_after=0, anchor=MSO_ANCHOR.TOP,
         caps=False, spacing=None):
    """``body`` is a string, or a list of (string, overrides) paragraph tuples."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

    paragraphs = body if isinstance(body, list) else [(body, {})]
    for i, item in enumerate(paragraphs):
        content, over = item if isinstance(item, tuple) else (item, {})
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = over.get("align", align)
        para.line_spacing = over.get("line", line)
        para.space_after = Pt(over.get("space_after", space_after))
        run = para.add_run()
        use_caps = over.get("caps", caps)
        run.text = content.upper() if use_caps else content
        font = run.font
        font.name = FONT
        font.size = Pt(over.get("size", size))
        font.bold = over.get("bold", bold)
        font.color.rgb = over.get("color", color)
        gap = over.get("spacing", spacing)
        if gap is not None:
            # Letter-spacing has no python-pptx setter; it is a run property.
            run.font._rPr.set("spc", str(int(gap * 100)))
    return box


def title(slide, label, sub=None):
    text(slide, Inches(0.6), Inches(0.45), Inches(12.1), Inches(0.7),
         label, size=27, bold=True, color=INK)
    rule(slide, Inches(0.62), Inches(1.16), Inches(0.9), PRIMARY, 2.25)
    if sub:
        text(slide, Inches(0.6), Inches(1.32), Inches(11.9), Inches(0.45),
             sub, size=12.5, color=INK_2)


def eyebrow(slide, x, y, w, label, color=INK_3):
    """Uppercase, tracked-out label. Latin only -- the app scopes this device to
    html[lang=en], because Devanagari, Tamil and Telugu have no letter case and
    tracking pushes matras off the consonants they belong to."""
    text(slide, x, y, w, Inches(0.24), label, size=9.5, bold=True,
         color=color, caps=True, spacing=0.09)


def page_number(slide, n, color=INK_3):
    text(slide, Inches(12.5), Inches(7.02), Inches(0.55), Inches(0.3),
         str(n), size=9.5, color=color, align=PP_ALIGN.RIGHT)


# ------------------------------------------------------------------ icons
# Stroked glyphs on a 24-unit grid, mirroring frontend/icons.js. Primitives:
#   ("l", x1, y1, x2, y2)      line
#   ("c", cx, cy, r)           circle outline
#   ("e", cx, cy, rx, ry)      ellipse outline
#   ("d", cx, cy, r)           filled dot
#   ("r", x, y, w, h, radius)  rounded rectangle outline
ICONS = {
    "mic":    [("r", 9, 3, 6, 11, 0.5), ("l", 5, 11, 5, 12), ("l", 19, 11, 19, 12),
               ("l", 5, 12, 19, 12), ("l", 12, 18, 12, 21)],
    "wallet": [("r", 3, 6, 18, 14, 0.18), ("l", 3, 10, 21, 10), ("d", 16.5, 15, 1.3)],
    "send":   [("l", 21, 3, 10.5, 13.5), ("l", 21, 3, 14.5, 21),
               ("l", 14.5, 21, 10.5, 13.5), ("l", 10.5, 13.5, 3, 9.5), ("l", 3, 9.5, 21, 3)],
    "scheme": [("r", 5, 3, 14, 18, 0.12), ("l", 9, 8, 15, 8), ("l", 9, 12, 15, 12),
               ("l", 9, 16, 12.5, 16)],
    "learn":  [("l", 3, 6, 3, 19), ("l", 3, 6, 11.4, 8), ("l", 11.4, 8, 11.4, 21),
               ("l", 3, 19, 11.4, 21), ("l", 21, 6, 21, 19), ("l", 21, 6, 12.6, 8),
               ("l", 12.6, 8, 12.6, 21), ("l", 21, 19, 12.6, 21)],
    "shield": [("l", 12, 3, 5, 6), ("l", 5, 6, 5, 12), ("l", 5, 12, 12, 21),
               ("l", 12, 21, 19, 12), ("l", 19, 12, 19, 6), ("l", 19, 6, 12, 3),
               ("l", 9, 12, 11.2, 14.2), ("l", 11.2, 14.2, 15.5, 10)],
    "scan":   [("l", 3, 8, 3, 5), ("l", 3, 5, 8, 5), ("l", 16, 5, 21, 5),
               ("l", 21, 5, 21, 8), ("l", 21, 16, 21, 19), ("l", 21, 19, 16, 19),
               ("l", 8, 19, 3, 19), ("l", 3, 19, 3, 16), ("l", 6, 12, 18, 12)],
    # "Offline" as a cloud plus a slash read as spectacles at 40px. An arrow
    # coming down into a tray says "held on the device" without ambiguity.
    "offline": [("l", 12, 3, 12, 14.5), ("l", 8, 10.5, 12, 14.5),
                ("l", 16, 10.5, 12, 14.5), ("l", 4, 17, 4, 20),
                ("l", 4, 20, 20, 20), ("l", 20, 17, 20, 20)],
    "growth": [("l", 3, 20, 21, 20), ("l", 4, 16, 9, 11), ("l", 9, 11, 12.5, 14.5),
               ("l", 12.5, 14.5, 20, 7), ("l", 15.5, 7, 20, 7), ("l", 20, 7, 20, 11.5)],
    "check":  [("c", 12, 12, 9), ("l", 7.5, 12.5, 10.8, 15.8), ("l", 10.8, 15.8, 16.5, 8.5)],
    "clock":  [("c", 12, 12, 9), ("l", 12, 7, 12, 12.4), ("l", 12, 12.4, 15.4, 14.2)],
    "layers": [("l", 12, 2.5, 21, 7), ("l", 21, 7, 12, 11.5), ("l", 12, 11.5, 3, 7),
               ("l", 3, 7, 12, 2.5), ("l", 3, 12, 12, 16.5), ("l", 12, 16.5, 21, 12),
               ("l", 3, 17, 12, 21.5), ("l", 12, 21.5, 21, 17)],
    "code":   [("l", 9, 7, 4, 12), ("l", 4, 12, 9, 17), ("l", 15, 7, 20, 12),
               ("l", 20, 12, 15, 17)],
    "globe":  [("c", 12, 12, 9), ("l", 3, 12, 21, 12), ("e", 12, 12, 4.2, 9)],
    "flag":   [("l", 5, 3, 5, 21), ("l", 5, 4, 19, 4), ("l", 19, 4, 19, 13),
               ("l", 19, 13, 5, 13)],
    "note":   [("r", 2.5, 6, 19, 12, 0.14), ("c", 12, 12, 2.8),
               ("l", 6, 10.5, 6, 13.5), ("l", 18, 10.5, 18, 13.5)],
    "user":   [("c", 12, 8, 3.6), ("l", 5.5, 20, 7, 16), ("l", 7, 16, 17, 16),
               ("l", 17, 16, 18.5, 20), ("l", 5.5, 20, 18.5, 20)],
}


def icon(slide, name, x, y, size, color=PRIMARY, weight=1.4):
    """Draw one glyph, scaled from the 24-unit grid into a square of ``size``."""
    unit = size / 24.0

    def P(v):
        return Emu(int(v * unit))

    for prim in ICONS.get(name, []):
        kind = prim[0]
        if kind == "l":
            _, x1, y1, x2, y2 = prim
            ln = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT, x + P(x1), y + P(y1), x + P(x2), y + P(y2))
            ln.line.color.rgb = color
            ln.line.width = Pt(weight)
        elif kind in ("c", "d", "e"):
            if kind == "e":
                _, cx, cy, rx, ry = prim
            else:
                _, cx, cy, r = prim
                rx = ry = r
            sh = flatten(slide.shapes.add_shape(
                MSO_SHAPE.OVAL, x + P(cx - rx), y + P(cy - ry), P(2 * rx), P(2 * ry)))
            if kind == "d":
                sh.fill.solid()
                sh.fill.fore_color.rgb = color
                sh.line.fill.background()
            else:
                sh.fill.background()
                sh.line.color.rgb = color
                sh.line.width = Pt(weight)
        elif kind == "r":
            _, rx, ry, rw, rh, rad = prim
            sh = flatten(slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, x + P(rx), y + P(ry), P(rw), P(rh)))
            sh.adjustments[0] = rad
            sh.fill.background()
            sh.line.color.rgb = color
            sh.line.width = Pt(weight)


def icon_chip(slide, name, x, y, box=Inches(0.62), tone=PRIMARY, tint=0.11,
              glyph=0.62, radius=0.22, base=SURFACE, glyph_color=None):
    """Tone-tinted rounded chip with the glyph centred in it -- the same device
    the six home tiles use, kept faint so six of them can share one screen
    without competing.

    ``base`` is the surface the tint is mixed into: white on a light slide, the
    dark green on the title slide. Mixing against the wrong ground is how you
    get a white chip on a white card.
    """
    chip = flatten(slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, box, box))
    chip.adjustments[0] = radius
    chip.fill.solid()
    chip.fill.fore_color.rgb = mix(tone, tint, base)
    chip.line.fill.background()

    g = int(box * glyph)
    icon(slide, name, Emu(int(x + (box - g) / 2)), Emu(int(y + (box - g) / 2)),
         g, glyph_color or tone)
    return chip


def blob(slide, cx, cy, r, color):
    """A large, quiet circle. The only decorative element in the deck, borrowed
    from the review-1 layout, and used once."""
    sh = flatten(slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Emu(int(cx - r)), Emu(int(cy - r)), Emu(int(2 * r)), Emu(int(2 * r))))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    return sh
