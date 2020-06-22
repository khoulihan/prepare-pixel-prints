#!/usr/bin/env python3

import sys
import argparse
from PIL import Image, ImageFilter, ImageColor
from pathlib import Path
import os
from os import path
import math


def colour(value):
    parsed = None
    try:
        parsed = ImageColor.getrgb(value)
    except ValueError:
        parsed = ImageColor.getrgb("#" + value)
    return parsed


def _verify_destination(destination, source):
    p = Path(destination)
    if not p.exists():
        p.mkdir()
    else:
        if p.is_file():
            raise NotADirectoryError()


def _verify_source(source):
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError()
    else:
        if not p.is_file():
            raise NotAFileError()


def _open(source):
    im = Image.open(source)
    return im


def _rotate(im, ccw):
    if ccw:
        return im.rotate(90, expand=True)
    else:
        return im.rotate(-90, expand=True)


def _scale_by_factor(im, factor):
    return im.resize((im.size[0] * factor, im.size[1] * factor))

# TODO: Use retain parameters to force cropping on a particular axis e.g. if 'left' and 'right' are present then only allow vertical crop?
# TODO: Adapt this to support reverse ratios, as sometimes it makes more sense to use those e.g. 0.75 vs 1.3333
def _crop_to_ratio(im, ratio, retain=[]):
    retain = [] if not retain else retain

    portrait = im.size[0] < im.size[1]
    l = max(im.size)
    s = min(im.size)

    # The idea here is that if the image is too skinny then it will be cropped vertically
    # if it is too fat then it will be cropped horizontally. Unclear if it actually works!
    crop_l = (l / s) > ratio
    crop_target = s * ratio if crop_l else l / ratio

    if crop_l and portrait or not crop_l and not portrait:
        crop_amount = im.size[1] - crop_target
        if 'top' in retain:
            y = 0
        elif 'bottom' in retain:
            y = math.ceil(crop_amount)
        else:
            y = math.ceil(crop_amount / 2)
        return im.crop((0, y, im.size[0], im.size[1] - (crop_amount - y)))
    else:
        crop_amount = im.size[0] - crop_target
        if 'left' in retain:
            x = 0
        elif 'right' in retain:
            x = math.ceil(crop_amount)
        else:
            x = math.ceil(crop_amount / 2)
        return im.crop((x, 0, im.size[0] - (crop_amount - x), im.size[1]))


# I think this will cover Pixels.com and other less fussy services as well
def _redbubble(im, source, destination, **kwargs):
    cw = _rotate(im, False)
    ccw = _rotate(im, True)

    # Scale by a factor that puts the image over 7632x6480
    l = max(im.size)
    s = min(im.size)
    lf = math.ceil(7632 / l)
    sf = math.ceil(6480 / s)
    f = max(lf, sf)

    for i, d in [(im, "redbubble"), (cw, "redbubble_cw"), (ccw, "redbubble_ccw")]:
        scaled = _scale_by_factor(i, f)
        _save(scaled, source, destination, d, "png")


def _displate(im, source, destination, retain, **kwargs):
    rgb = im.convert("RGB")

    # Crop to a 1.4:1 ratio
    cropped = _crop_to_ratio(rgb, 1.4, retain)

    # Scale by a factor that puts the smallest side over 10000 pixels
    s = min(cropped.size)
    f = math.ceil(10000 / s)

    scaled = _scale_by_factor(cropped, f)
    _save(scaled, source, destination, "displate", "jpg")


# These are done by aspect ratio because a single file can fit many sizes, since there are no borders
# to worry about. The sizes are just for selection on the command line
printful_posters = (
    (1.25, "printful_poster_in_4-5", ((8, 10), (16, 20))),
    (1.0, "printful_poster_in_1-1", ((10, 10), (12, 12), (14, 14), (16, 16), (18, 18))),
    (1.33, "printful_poster_in_cm_3-4", ((12, 16), (18, 24), (30, 40))),
    (1.5, "printful_poster_in_2-3", ((12, 18), (24, 36))),
    (1.43, "printful_poster_cm_7-10", ((21, 30), (70, 100))),
    (1.4, "printful_poster_cm_5-7", ((50, 70),))
)

printful_canvases = (
    ((12, 12), 300, "printful_canvas_12-12"),
    ((12, 16), 300, "printful_canvas_12-16"),
    ((16, 16), 300, "printful_canvas_16-16"),
    ((16, 20), 300, "printful_canvas_16-20"),
    ((18, 24), 250, "printful_canvas_18-24"), # Reduced DPI to prevent "DecompressionBomb" warning
    ((24, 36), 200, "printful_canvas_24-36"),
)

# Don't forget the DPI
printful_mat_posters = (
    ((21, 30), 3.5, 300, "printful_poster_mat_21-30"),
    ((30, 40), 5.5, 300, "printful_poster_mat_30-40"),
    ((50, 70), 9.0, 300, "printful_poster_mat_50-70"),
    ((61, 91), 11.5, 300, "printful_poster_mat_61-91"),
)


def _printful(im, source, destination, canvas_edge_type, canvas_edge_colour, logo, products, sizes, retain, **kwargs):
    # Straightforward posters with no padding
    if not products or 'poster' in products:
        _printful_posters(im, source, destination, sizes, retain)

    # Canvases
    if not products or 'canvas' in products:
        _printful_canvases(im, source, destination, canvas_edge_type, canvas_edge_colour, logo, sizes, retain)

    # Posters with mat
    if not products or 'poster_with_mat' in products:
        _printful_posters_with_mat(im, source, destination, sizes, retain)


def _printful_posters(im, source, destination, sizes, retain):
    for ratio, description, match_sizes in printful_posters:
        parsed_sizes = ["{0}x{1}".format(*s) for s in match_sizes]
        if not sizes or any(s in parsed_sizes for s in sizes):
            cropped = _crop_to_ratio(im, ratio, retain)
            # Scale by a factor that puts the smallest side over 10000 pixels
            s = min(cropped.size)
            f = math.ceil(10000 / s)
            scaled = _scale_by_factor(cropped, f)
            _save(scaled, source, destination, description, "png")


def _printful_posters_with_mat(im, source, destination, sizes, retain):
    for full, mat, dpi, description in printful_mat_posters:
        full_parsed = "{0}x{1}".format(*full)
        if not sizes or full_parsed in sizes:
            mat_2 = mat * 2
            # Convert DPI to pixels per cm
            ppcm = math.ceil(dpi * 0.393701)
            inner = (full[0] - mat_2, full[1] - mat_2)
            ratio = inner[1] / inner[0]
            cropped = _crop_to_ratio(im, ratio, retain)
            # Scale by a factor that puts the smallest side over the minimum to achieve the desired DPI
            s = min(cropped.size)
            f = math.ceil(inner[0] * ppcm / s)
            scaled = _scale_by_factor(cropped, f)
            portrait = scaled.size[0] < scaled.size[1]
            inner_pivoted = inner if portrait else (inner[1], inner[0])
            full_pivoted = full if portrait else (full[1], full[0])
            cm = scaled.size[0] / inner_pivoted[0]
            bordered_size = (
                math.ceil((scaled.size[0] / inner_pivoted[0]) * (inner_pivoted[0] + mat_2)),
                math.ceil((scaled.size[1] / inner_pivoted[1]) * (inner_pivoted[1] + mat_2))
            )
            full_im = Image.new("RGBA", bordered_size)
            inner_paste_location = (math.ceil((bordered_size[0] - scaled.size[0]) / 2), math.ceil((bordered_size[1] - scaled.size[1]) / 2))
            full_im.alpha_composite(scaled, inner_paste_location)

            _save(full_im, source, destination, description, "png")


def _printful_canvases(im, source, destination, canvas_edge_type, edge_colour, logo, sizes, retain):
    logo_im = None
    if logo:
        logo_im = _open(logo)
        logo_im = logo_im.transpose(Image.ROTATE_180)

    for inner, dpi, description in printful_canvases:
        inner_parsed = "{0}x{1}".format(*inner)
        if not sizes or inner_parsed in sizes:
            ratio = inner[1] / inner[0] #if im.size[0] > im.size[1] else inner[1] / inner[0]
            cropped = _crop_to_ratio(im, ratio, retain)
            # Scale by a factor that puts the smallest side over the minimum to achieve the desired DPI
            s = min(cropped.size)
            f = math.ceil(inner[0] * dpi / s)
            scaled = _scale_by_factor(cropped, f)
            portrait = scaled.size[0] < scaled.size[1]
            inner_pivoted = inner if portrait else (inner[1], inner[0])
            inch = scaled.size[0] / inner_pivoted[0]
            bordered_size = (
                math.ceil((scaled.size[0] / inner_pivoted[0]) * (inner_pivoted[0] + 6)),
                math.ceil((scaled.size[1] / inner_pivoted[1]) * (inner_pivoted[1] + 6))
            )
            edge_size = (
                math.ceil((scaled.size[0] / inner_pivoted[0]) * (inner_pivoted[0] + 3)),
                math.ceil((scaled.size[1] / inner_pivoted[1]) * (inner_pivoted[1] + 3))
            )

            edge = None

            if any(edge_type in canvas_edge_type for edge_type in ("extendblur", "solid")):
                edge = Image.new("RGBA", edge_size, edge_colour)

            if any(edge_type in canvas_edge_type for edge_type in ("extend", "blurextend", "extendblur")):
                # Edge slices to pull around the edge of the canvas
                left = scaled.crop((0, 0, 1, scaled.size[1]))
                right = scaled.crop((scaled.size[0] - 1, 0, scaled.size[0], scaled.size[1]))
                top = scaled.crop((0, 0, scaled.size[0], 1))
                bottom = scaled.crop((0, scaled.size[1] - 1, scaled.size[0], scaled.size[1]))

            # Blur edging - didn't really like it...
            if any(edge_type in canvas_edge_type for edge_type in ("blur", "blurextend")):
                edge = scaled.resize(edge_size)
                edge = edge.filter(ImageFilter.GaussianBlur(100))

            full = Image.new("RGBA", bordered_size)
            #edge_paste_location = (math.ceil((bordered_size[0] - blurred_edge.size[0]) / 2), math.ceil((bordered_size[1] - blurred_edge.size[1]) / 2))
            edge_paste_location = (math.ceil((bordered_size[0] - edge_size[0]) / 2), math.ceil((bordered_size[1] - edge_size[1]) / 2))
            inner_paste_location = (math.ceil((bordered_size[0] - scaled.size[0]) / 2), math.ceil((bordered_size[1] - scaled.size[1]) / 2))
            # Inner location within the edge image
            inner_edge_location = (math.ceil((edge_size[0] - scaled.size[0]) / 2), math.ceil((edge_size[1] - scaled.size[1]) / 2))

            if any(edge_type in canvas_edge_type for edge_type in ("extend", "blurextend", "extendblur")):
                if not edge:
                    edge = Image.new("RGBA", edge_size)
                for x in range(0, inner_edge_location[0] + 200):
                    edge.paste(left, (x, inner_edge_location[1]))
                for x in range(inner_edge_location[0] + scaled.size[0] - 200, edge_size[0]):
                    edge.paste(right, (x, inner_edge_location[1]))
                for y in range(0, inner_edge_location[1] + 200):
                    edge.paste(top, (inner_edge_location[0], y))
                for y in range(inner_edge_location[1] + scaled.size[1] - 200, edge_size[1]):
                    edge.paste(bottom, (inner_edge_location[0], y))

            if "extendblur" in canvas_edge_type:
                edge = edge.filter(ImageFilter.GaussianBlur(10))

            full.alpha_composite(edge, edge_paste_location)
            full.alpha_composite(scaled, inner_paste_location)

            # Add logo
            if logo:
                logo_scaled = logo_im.resize((math.ceil(logo_im.size[0] * (math.ceil(inch * 0.5) / logo_im.size[1] )), math.ceil(inch * 0.5)), Image.LANCZOS)
                logo_paste_location = (math.ceil((inch * ((inner_pivoted[0] / 2.0) + 3.0)) - logo_scaled.size[0] / 2.0), math.ceil(inch * (inner_pivoted[1] + 4.5 + 0.1)))
                full.paste(logo_scaled, logo_paste_location)

            _save(full, source, destination, description, "png")


def _inprnt(im, source, destination, **kwargs):
    # Max resolution 6600 x 10200
    # JPG or TIFF at full quality
    # Scale by a factor that puts the smallest side over 10000 pixels
    rgb = im.convert('RGB')
    s = min(rgb.size)
    l = max(rgb.size)
    f = math.floor(10200 / l)
    if f * s > 6600:
        f = math.floor(6600 / s)
    scaled = _scale_by_factor(rgb, f)
    _save(scaled, source, destination, "inprnt", "jpg")


def _save(im, source, destination, description, ext):
    ps = Path(source)
    pd = Path(destination)
    filename = "{0}_{1}.{2}".format(ps.stem, description, ext)
    im.save(pd / filename, quality=100)


def _parse_arguments():
    parser = argparse.ArgumentParser(description="Prepare print files for various print services.")
    parser.add_argument("source", type=str, action="store", help="source file")
    parser.add_argument("-d", "--debug", action="store_true", dest="debug", help="print debugging information")
    parser.add_argument("--destination", dest="destination", metavar='D', type=str, action="store", default="prints", help="destination directory")

    # Cropping instructions
    parser.add_argument("--retain", dest="retain", metavar='E', type=str, action="store", choices=['left', 'right', 'top', 'bottom'], nargs='*', help="sides to retain during cropping")

    # Options specifically related to canvases
    parser.add_argument("--edge", dest="canvas_edge_type", metavar='E', type=str, action="store", choices=['extend', 'blur', 'blurextend', 'extendblur', 'solid'], default="extend", nargs='*', help="method(s) to use for canvas edges")
    parser.add_argument("--edgecolour", dest="canvas_edge_colour", metavar='C', type=colour, action="store", help="solid colour for canvas edges")
    parser.add_argument("-l", "--logo", dest="logo", metavar='L', type=str, action="store", help="logo to include on products that support it")

    # Limit to specific services
    parser.add_argument("--redbubble", dest="services", action='append_const', const=_redbubble, help="produce files for Redbubble (and miscellaneous services)")
    parser.add_argument("--displate", dest="services", action='append_const', const=_displate, help="produce files for Displate")
    #parser.add_argument("--other", dest="services", action='append_const', const=_redbubble, help="produce files for miscellaneous services")
    parser.add_argument("--printful", dest="services", action='append_const', const=_printful, help="produce files for Printful")
    parser.add_argument("--inprnt", dest="services", action='append_const', const=_inprnt, help="produce files for InPRNT")

    # Limit further to specific products and/or sizes, where applicable
    parser.add_argument("-p", "--products", dest="products", metavar='P', type=str, action="store", nargs='*', choices=['poster', 'canvas', 'poster_with_mat'], help="product(s) to create print files for, if a service has more than one type. Ignored otherwise.")
    parser.add_argument("-s", "--sizes", dest="sizes", metavar='WxH', type=str, action="store", nargs='*', help="size(s) of products to create files for, e.g. 12x16. Use portrait orientation regardless of art orientation")

    args = parser.parse_args()
    return args


def _main():
    args = _parse_arguments()
    try:
        try:
            _verify_source(args.source)
        except FileNotFoundError:
            print ("The specified source does not exist.")
            sys.exit(1)
        except NotAFileError:
            print ("The specified source is not a file.")
            sys.exit(1)

        try:
            _verify_destination(args.destination, args.source)
        except NotADirectoryError:
            print ("The specified destination is not a directory.")
            sys.exit(1)
        except FileNotFoundError:
            print ("The specified destination directory could not be created because of missing parents.")
            sys.exit(1)
        except PermissionError:
            print ("The destination directory could not be created due to inadequate permissions.")
            sys.exit(1)

        im = None
        try:
            im = _open(args.source)
        except IOError:
            print ("The specified source could not be opened as an image.")
            sys.exit(1)

        if args.services:
            services = args.services
        else:
            services = [_redbubble, _displate, _printful, _inprnt]

        for service in services:
            service(im, **vars(args))

    except KeyboardInterrupt:
        # TODO: Maybe track some statistics and print them on exit.
        print()
        sys.exit(0)


if __name__ == "__main__":
    _main()
