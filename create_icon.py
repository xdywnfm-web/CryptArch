"""Create a self-contained, multi-resolution Windows icon for CryptArch."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(exist_ok=True)
size = 1024
canvas = Image.new("RGBA", (size, size))
draw = ImageDraw.Draw(canvas)

# Rounded dark navy tile.
draw.rounded_rectangle((24, 24, 1000, 1000), radius=230, fill=(15, 25, 40, 255))
draw.rounded_rectangle((36, 36, 988, 988), radius=218, outline=(52, 79, 99, 255), width=12)

# Subtle glow behind the compact archive emblem.
glow = Image.new("RGBA", canvas.size)
gd = ImageDraw.Draw(glow)
gd.rounded_rectangle((205, 252, 819, 776), radius=135, fill=(20, 182, 160, 100))
glow = glow.filter(ImageFilter.GaussianBlur(85))
canvas = Image.alpha_composite(canvas, glow)
draw = ImageDraw.Draw(canvas)

# Archive body with a simple, bold silhouette.
draw.rounded_rectangle((205, 278, 819, 766), radius=125, fill=(72, 215, 190, 255))
draw.rounded_rectangle((242, 315, 782, 729), radius=94, fill=(20, 52, 64, 255))
draw.rounded_rectangle((272, 344, 752, 700), radius=73, fill=(17, 37, 50, 255))

# Play button and inward-pointing compression chevrons.
draw.polygon([(456, 410), (456, 637), (622, 524)], fill=(183, 255, 234, 255))
draw.line([(319, 451), (371, 523), (319, 595)], fill=(101, 232, 207, 255), width=34, joint="curve")
draw.line([(705, 451), (653, 523), (705, 595)], fill=(101, 232, 207, 255), width=34, joint="curve")
draw.rounded_rectangle((369, 237, 655, 289), radius=26, fill=(151, 245, 224, 255))

master = canvas.resize((256, 256), Image.Resampling.LANCZOS)
master.save(OUT / "CryptArch.png")
master.save(OUT / "CryptArch.ico", format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(OUT / "CryptArch.ico")
