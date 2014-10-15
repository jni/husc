#!/bin/env python

# standard library
import os
import sys
import argparse
import itertools as it

# dependencies
import numpy as np
import mahotas as mh
import pandas as pd
from skimage import io, img_as_ubyte

# local imports
from . import io as hio
from . import screens
from . import preprocess as pre


parser = argparse.ArgumentParser(description="Run the HUSC functions.")
subpar = parser.add_subparsers()


crop = subpar.add_parser('crop', help="Crop images.")
crop.add_argument('crops', nargs=4, metavar='INT',
                  help='xstart, xstop, ystart, ystop. "None" also allowed.')
crop.add_argument('images', nargs='+', metavar='IM', help="The input images.")
crop.add_argument('-o', '--output-suffix',
                  default='.crop.tif', metavar='SUFFIX',
                  help="What suffix to attach to the cropped images.")
crop.add_argument('-O', '--output-dir',
                  help="Directory in which to output the cropped images.")


mask = subpar.add_parser('mask', help="Estimate a mask over image artifacts.")
mask.add_argument('images', nargs='+', metavar='IM', help="The input images.")
mask.add_argument('-o', '--offset', metavar='INT', default=0, type=int,
                  help='Offset the automatic mask threshold by this amount.')
mask.add_argument('-v', '--verbose', action='store_true',
                  help='Print runtime information to stdout.')
mask.add_argument('-c', '--close', metavar='RADIUS', default=0, type=int,
                  help='Perform morphological closing of masks of this radius.')
mask.add_argument('-e', '--erode', metavar='RADIUS', default=0, type=int,
                  help='Perform morphological erosion of masks of this radius.')


illum = subpar.add_parser('illum',
                          help="Estimate and correct illumination.")
illum.add_argument('images', nargs='*', metavar='IMG', default=[],
                   help="The input images.")
illum.add_argument('-f', '--file-list', type=lambda x: open(x, 'r'),
                   metavar='FN',
                   help='Text file with one image filename per line.')
illum.add_argument('-o', '--output-suffix',
                   default='.illum.tif', metavar='SUFFIX',
                   help="What suffix to attach to the corrected images.")
illum.add_argument('-M', '--use-mask', action='store_true',
                   help="Mask out abnormally bright parts of the image.")
illum.add_argument('-m', '--mask-offset', metavar='INT', default=0, type=int,
                  help='Offset the automatic mask threshold by this amount.')
illum.add_argument('-c', '--mask-close', metavar='RADIUS', default=0, type=int,
                  help='Perform morphological closing of masks of this radius.')
illum.add_argument('-e', '--mask-erode', metavar='RADIUS', default=0, type=int,
                  help='Perform morphological erosion of masks of this radius.')
illum.add_argument('-l', '--stretchlim', metavar='[0.0-1.0]', type=float,
                   default=0.0, help='Stretch image range before all else.')
illum.add_argument('-L', '--stretchlim-output', metavar='[0.0-1.0]', type=float,
                   default=0.0, help='Stretch image range before output.')
illum.add_argument('-q', '--quantile', metavar='[0.0-1.0]', type=float, 
                   default=0.05,
                   help='Use this quantile to determine illumination.')
illum.add_argument('-r', '--radius', metavar='INT', type=int, default=51,
                   help='Radius in which to find quantile.')
illum.add_argument('-s', '--save-illumination', metavar='FN',
                   help='Save the illumination field to a file.')
illum.add_argument('-v', '--verbose', action='store_true',
                   help='Print runtime information to stdout.')


stitch = subpar.add_parser('stitch', 
                            help="Stitch images by quadrant.")
stitch.add_argument('images', nargs='*', metavar='IM',
                    help="The input images.")


cat = subpar.add_parser('cat',
                        help="Glue the different image channels together.")
cat.add_argument('images', nargs='*', metavar='IM',
                 help="The input images.")


features = subpar.add_parser('features',
                             help="Map images to feature vectors.")
features.add_argument('images', nargs='*', metavar='IM',
                      help="The input images.")
features.add_argument('output', metavar='OUTFN',
                      help="The output HDF5 filename.")
features.add_argument('-s', '--screen', default='myofusion',
                      help="The name of the screen being run. Feature maps "
                           "appropriate for the screen should be in the "
                           "'screens' package.")


def get_command(argv):
    """Get the command name used from the command line.

    Parameters
    ----------
    argv : [string]
        The argument vector.

    Returns
    -------
    cmd : string
        The command name.
    """
    return argv[1]


def main():
    """Run the command-line interface."""
    args = parser.parse_args()
    cmd = get_command(sys.argv)
    if cmd == 'crop':
        run_crop(args)
    elif cmd == 'mask':
        run_mask(args)
    elif cmd == 'illum':
        run_illum(args)
    elif cmd == 'stitch':
        run_stitch(args)
    elif cmd == 'cat':
        run_cat(args)
    elif cmd == 'features':
        run_features(args)
    else:
        sys.stderr.write("Error: command %s not found. Run %s -h for help." %
                         (cmd, sys.argv[0]))
        sys.exit(2) # 2 is commonly a command-line error


def run_crop(args):
    """Run image cropping."""
    crops = []
    for c in args.crops:
        try:
            crops.append(int(c))
        except ValueError:
            crops.append(None)
    xstart, xstop, ystart, ystop = crops
    slices = (slice(xstart, xstop), slice(ystart, ystop))
    for imfn in args.images:
        im = io.imread(imfn)
        imout = pre.crop(im, slices)
        fnout = os.path.splitext(imfn)[0] + args.output_suffix
        if args.output_dir is not None:
            fnout = os.path.join(args.output_dir, os.path.split(fnout)[1])
        mh.imsave(fnout, imout)


def run_mask(args):
    """Run mask generation."""
    n, m = pre.write_max_masks(args.images, args.offset, args.close, args.erode)
    if args.verbose:
        print("%i masks created out of %i images processed" % (n, m))


def run_illum(args):
    """Run illumination correction.

    Parameters
    ----------
    args : argparse.Namespace
        The arguments parsed by the argparse library.
    """
    if args.file_list is not None:
        args.images.extend([fn.rstrip() for fn in args.file_list])
    il = pre.find_background_illumination(args.images, args.radius,
                                          args.quantile, args.stretchlim,
                                          args.use_mask, args.mask_offset,
                                          args.mask_close, args.mask_erode)
    if args.verbose:
        print 'illumination field:', type(il), il.dtype, il.min(), il.max()
    if args.save_illumination is not None:
        io.imsave(args.save_illumination, il / il.max())
    base_fns = [pre.basefn(fn) for fn in args.images]
    ims_out = [fn + args.output_suffix for fn in base_fns]
    mask_fns = [fn + '.mask.tif' for fn in base_fns]
    ims = (mh.imread(fn) for fn in args.images)
    for im, fout, mask_fn in it.izip(ims, ims_out, mask_fns):
        if os.path.isfile(mask_fn):
            mask = mh.imread(mask_fn).astype(bool)
        else:
            mask = np.ones(im.shape, bool)
        im = pre.correct_image_illumination(im, il,
                                            args.stretchlim_output, mask)
        io.imsave(fout, im)


def run_stitch(args):
    """Run stitching.

    Parameters
    ----------
    args : argparse.Namespace
        The arguments parsed by the argparse library.
    """
    pre.run_quadrant_stitch(args.images)


def run_cat(args):
    """Run channel concatenation.

    Parameters
    ----------
    args : argparse.Namespace
        The arguments parsed by the argparse library.
    """
    ims = it.imap(mh.imread, args.images)
    ims_out = hio.cat_channels(ims)
    out_fns = [os.path.splitext(fn)[0] + '.chs.tif' for fn in args.images[::3]]
    for im, fn in it.izip(ims_out, out_fns):
        try:
            mh.imsave(fn, im)
        except ValueError:
            im = img_as_ubyte(pre.stretchlim(im, 0.05, 0.95))
            mh.imsave(fn, im)


def run_features(args):
    """Run image feature computation.

    Parameters
    ----------
    args : argparse.Namespace
        The arguments parsed by the argparse library.
    """
    images = it.imap(mh.imread, args.images)
    screen_info = screens.d[args.screen]
    index_function, fmap = screen_info['index'], screen_info['fmap']
    f0, feature_names = fmap(images.next())
    feature_vectors = [f0] + [fmap(im)[0] for im in images]
    data = pd.DataFrame(np.vstack(feature_vectors),
                        index=map(index_function, args.images),
                        columns=feature_names)
    data.to_hdf(args.output, key='data')
    with open(args.output[:-2] + 'filenames.txt', 'w') as fout:
        fout.writelines((fn + '\n' for fn in args.images))


if __name__ == '__main__':
    main()

