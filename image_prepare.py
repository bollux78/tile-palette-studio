"""Non-destructive source edits, shared by preview and all export paths."""
from PIL import ImageEnhance
import math


def prepare_image(image, options):
    image.seek(0)
    image = image.convert('RGBA')
    box = options.get('crop')
    if box is not None:
        if (len(box) != 4 or any(type(v) is not int for v in box)
                or not 0 <= box[0] < box[2] <= image.width
                or not 0 <= box[1] < box[3] <= image.height):
            raise ValueError('Recorte fora dos limites da imagem original.')
        image = image.crop(tuple(box))
    alpha = image.getchannel('A')
    rgb = image.convert('RGB')
    for key, enhancer, maximum in (
        ('brightness', ImageEnhance.Brightness, 2),
        ('contrast', ImageEnhance.Contrast, 2),
        ('sharpness', ImageEnhance.Sharpness, 3),
    ):
        factor = float(options.get(key, 1))
        if not math.isfinite(factor) or not 0 <= factor <= maximum:
            raise ValueError('Ajuste de imagem inválido: ' + key)
        if factor != 1:
            rgb = enhancer(rgb).enhance(factor)
    rgb.putalpha(alpha)
    return rgb
