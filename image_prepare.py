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


def resize_image(image, width, height, resample, keep_aspect=True,
                 pixel_aspect=1.0, fit='contain', background='#000000', preserve_alpha=False):
    """Resize for the DISPLAY pixel shape, rather than assuming square pixels.

    pixel_aspect is displayed pixel width / height. The returned PNG remains a
    native-resolution raster; displaying its width times PAR restores geometry.
    'contain' preserves the whole source, 'cover' fills by cropping the excess.
    """
    from PIL import Image,ImageColor
    if (type(width) is not int or type(height) is not int or not 1<=width<=8192
            or not 1<=height<=8192 or width*height>16_000_000):
        raise ValueError('Dimensões inválidas para redimensionamento.')
    pixel_aspect=float(pixel_aspect)
    if not math.isfinite(pixel_aspect) or not .25<=pixel_aspect<=4:
        raise ValueError('Aspecto de pixel inválido.')
    if fit not in ('contain','cover'):
        raise ValueError('Ajuste ao quadro inválido.')
    image=image.convert('RGBA')
    if keep_aspect and fit=='cover':
        # Crop the source rectangle before resizing. Extremely wide/tall inputs
        # must not allocate an enormous intermediate just to crop it away.
        ratio=width*pixel_aspect/height
        if image.width/image.height>ratio:
            cw=image.height*ratio
            box=((image.width-cw)/2,0,(image.width+cw)/2,image.height)
        else:
            ch=image.width/ratio
            box=(0,(image.height-ch)/2,image.width,(image.height+ch)/2)
        fitted=image.resize((width,height),resample,box=box)
    elif keep_aspect:
        scale=min(width*pixel_aspect/image.width,height/image.height)
        rw=min(width,max(1,round(image.width*scale/pixel_aspect)))
        rh=min(height,max(1,round(image.height*scale)))
        fitted=image.resize((rw,rh),resample)
    else:fitted=image.resize((width,height),resample)
    color=ImageColor.getrgb(background)
    canvas=Image.new('RGBA',(width,height),(0,0,0,0) if preserve_alpha else (*color,255))
    position=((width-fitted.width)//2,(height-fitted.height)//2)
    if preserve_alpha:canvas.paste(fitted,position)
    else:canvas.alpha_composite(fitted,position)
    return canvas
