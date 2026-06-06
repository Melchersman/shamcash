"""QR code image generation helpers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Optional, Tuple, Union


Color = Tuple[int, int, int]
PathLike = Union[str, Path]


def _hex_to_rgb(value: str) -> Color:
    text = str(value).strip().lstrip("#")
    if len(text) != 6:
        raise ValueError("colors must be 6-digit hex values")

    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError("colors must be valid 6-digit hex values") from exc


def _mix(a: Color, b: Color, amount: float) -> Color:
    amount = max(0.0, min(1.0, amount))
    return tuple(round(a[index] + (b[index] - a[index]) * amount) for index in range(3))  # type: ignore[return-value]


def _relative_luminance(color: Color) -> float:
    def channel(value: int) -> float:
        value = value / 255
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = color
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def _contrast_ratio(a: Color, b: Color) -> float:
    first = _relative_luminance(a)
    second = _relative_luminance(b)

    lighter = max(first, second)
    darker = min(first, second)

    return (lighter + 0.05) / (darker + 0.05)


def _text_width(draw: Any, text: str, font: Any) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return int(box[2] - box[0])


def _text_height(draw: Any, text: str, font: Any) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return int(box[3] - box[1])


def _load_font(image_font: Any, size: int, *, bold: bool = False) -> Any:
    candidates = (
        ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf")
        if bold
        else ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf")
    )

    for name in candidates:
        try:
            return image_font.truetype(name, size)
        except OSError:
            continue

    return image_font.load_default()


def _ellipsize(draw: Any, text: str, font: Any, max_width: int) -> str:
    text = text.rstrip()
    if _text_width(draw, text, font) <= max_width:
        return text

    suffix = "…"
    while text and _text_width(draw, f"{text}{suffix}", font) > max_width:
        text = text[:-1].rstrip()

    return f"{text}{suffix}" if text else suffix


def _wrap_text(draw: Any, text: str, font: Any, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words or max_lines < 1:
        return []

    lines: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"

        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = word
        else:
            lines.append(_ellipsize(draw, word, font, max_width))
            current = ""

        if len(lines) >= max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines:
        remaining = " ".join(words)
        joined = " ".join(lines)
        if len(joined) < len(remaining):
            lines[-1] = _ellipsize(draw, lines[-1], font, max_width)

    return lines[:max_lines]


def _default_logo_path() -> Optional[Path]:
    path = Path(__file__).resolve().parent / "assets" / "shamcash_logo.png"
    return path if path.is_file() else None


def _load_logo_image(
    image_module: Any,
    logo_path: PathLike,
    *,
    max_width: int,
    max_height: int,
) -> Any:
    path = Path(logo_path)
    if not path.is_file():
        raise FileNotFoundError(f"logo file was not found: {path}")

    if path.suffix.lower() == ".svg":
        try:
            import cairosvg
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "SVG logo rendering requires cairosvg. "
                "Install with `pip install shamcash[qr]` or pass a PNG logo."
            ) from exc

        png_bytes = cairosvg.svg2png(
            url=str(path),
            output_width=max_width * 3,
            output_height=max_height * 3,
        )
        logo = image_module.open(BytesIO(png_bytes))
    else:
        logo = image_module.open(path)

    logo = logo.convert("RGBA")
    logo.thumbnail((max_width, max_height), image_module.LANCZOS)
    return logo


def create_qr_code(
    payload: str,
    path: Optional[Union[str, Path]] = None,
    *,
    size: int = 1024,
    border: int = 4,
    foreground: str = "#253C96",
    background: str = "#F1F3F7",
    canvas_background: str = "#FFFFFF",
    panel_border_color: str = "#C9D2E6",
    caption: Optional[str] = None,
    caption_color: Optional[str] = None,
    caption_font_size: Optional[int] = None,
    caption_max_lines: int = 2,
    caption_spacing: Optional[int] = None,
    logo_path: Optional[Union[str, Path]] = None,
    logo_enabled: bool = True,
    module_border_color: Optional[str] = None,
    module_border_width: int = 1,
) -> Any:
    """Create a QR code image.

    Returns a PIL Image. If path is provided, the image is saved.
    """
    text = str(payload or "").strip()
    if not text:
        raise ValueError("payload must be a non-empty string")

    if size < 320:
        raise ValueError("size must be at least 320 pixels")

    if border < 4:
        raise ValueError("border must be at least 4 for reliable scanning")

    if caption_max_lines < 1:
        raise ValueError("caption_max_lines must be at least 1")

    if module_border_width < 0:
        raise ValueError("module_border_width must be 0 or greater")

    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "QR generation requires qrcode and Pillow. Install with `pip install shamcash[qr]`."
        ) from exc

    fg = _hex_to_rgb(foreground)
    bg = _hex_to_rgb(background)
    canvas_bg = _hex_to_rgb(canvas_background)
    panel_border = _hex_to_rgb(panel_border_color)
    cap_color = _hex_to_rgb(caption_color or foreground)

    if _contrast_ratio(fg, bg) < 4.5:
        raise ValueError("foreground and background colors do not have enough contrast")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    module_count = len(matrix)

    panel_margin = max(20, size // 48)
    inner_padding = max(20, size // 26)
    panel_radius = max(24, size // 30)

    tab_width = max(150, size // 4)
    tab_height = max(110, size // 7)
    panel_top = tab_height // 2

    content_size = size - (panel_margin + inner_padding) * 2
    box_size = max(1, content_size // module_count)
    qr_size = module_count * box_size

    qr_x = (size - qr_size) // 2
    qr_y = panel_top + (size - qr_size) // 2

    if module_border_color is None:
        module_border = _mix(fg, bg, 0.42)
    else:
        module_border = _hex_to_rgb(module_border_color)

    caption_text = str(caption or "").strip()
    caption_lines: list[str] = []
    caption_area = 0
    caption_font = None
    line_gap = 0

    if caption_text:
        font_size = caption_font_size or max(20, size // 34)
        caption_font = _load_font(ImageFont, font_size)

        scratch = Image.new("RGB", (1, 1), canvas_bg)
        scratch_draw = ImageDraw.Draw(scratch)

        max_caption_width = size - max(64, size // 8)
        caption_lines = _wrap_text(
            scratch_draw,
            caption_text,
            caption_font,
            max_caption_width,
            caption_max_lines,
        )

        line_gap = max(4, font_size // 5)
        text_height = sum(_text_height(scratch_draw, line, caption_font) for line in caption_lines)
        if len(caption_lines) > 1:
            text_height += line_gap * (len(caption_lines) - 1)

        spacing = caption_spacing if caption_spacing is not None else max(10, size // 90)
        bottom_padding = max(18, size // 60)
        caption_area = spacing + text_height + bottom_padding

    canvas_height = panel_top + size + caption_area
    image = Image.new("RGB", (size, canvas_height), canvas_bg)
    draw = ImageDraw.Draw(image)

    panel_rect = [
        panel_margin,
        panel_top + panel_margin,
        size - panel_margin,
        panel_top + size - panel_margin,
    ]
    draw.rounded_rectangle(
        panel_rect,
        radius=panel_radius,
        fill=bg,
        outline=panel_border,
        width=max(2, size // 320),
    )

    tab_left = (size - tab_width) // 2
    tab_rect = [tab_left, 0, tab_left + tab_width, tab_height]
    draw.rounded_rectangle(
        tab_rect,
        radius=max(24, tab_height // 4),
        fill=bg,
        outline=panel_border,
        width=max(2, size // 320),
    )

    for row_index, row in enumerate(matrix):
        for col_index, enabled in enumerate(row):
            if not enabled:
                continue

            x0 = qr_x + col_index * box_size
            y0 = qr_y + row_index * box_size
            x1 = x0 + box_size - 1
            y1 = y0 + box_size - 1

            outline = None
            outline_width = 0
            if module_border_width > 0 and box_size >= 6:
                outline = module_border
                outline_width = module_border_width

            draw.rectangle(
                [x0, y0, x1, y1],
                fill=fg,
                outline=outline,
                width=outline_width,
            )

    if logo_enabled:
        resolved_logo_path: Optional[Union[str, Path]] = logo_path or _default_logo_path()
        if resolved_logo_path:
            logo_max_width = int(tab_width * 0.58)
            logo_max_height = int(tab_height * 0.58)
            logo = _load_logo_image(
                Image,
                resolved_logo_path,
                max_width=logo_max_width,
                max_height=logo_max_height,
            )

            logo_x = (size - logo.width) // 2
            logo_y = (tab_height - logo.height) // 2
            image.paste(logo, (logo_x, logo_y), logo)

    if caption_lines and caption_font is not None:
        text_draw = ImageDraw.Draw(image)
        text_y = panel_top + size + (caption_spacing if caption_spacing is not None else max(10, size // 90))

        for line in caption_lines:
            box = text_draw.textbbox((0, 0), line, font=caption_font)
            line_width = box[2] - box[0]
            line_height = box[3] - box[1]

            text_draw.text(
                ((size - line_width) / 2, text_y),
                line,
                fill=cap_color,
                font=caption_font,
            )

            text_y += line_height + line_gap

    if path is not None:
        image.save(Path(path))

    return image