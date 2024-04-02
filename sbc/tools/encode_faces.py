#!/usr/bin/env python3
import sys
import argparse
import logging
import pickle
import cv2
import face_recognition as freg

from functools import reduce
from pathlib import Path
from cv2.typing import MatLike
from numpy.typing import NDArray


SUPPORTED_DETECTION_MODELS = [ 'hog', 'cnn' ]


def log_imread(image: Path) -> MatLike:
    logging.info('Reading image \'%s\'', image)
    return cv2.imread(str(image))

def convert_to_rgb(image: MatLike) -> MatLike:
   logging.debug('Converting image from BGR to RGB...')
   return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def localize_faces_and_compute_encodings(rgb: MatLike, model: str) -> list[NDArray]:
   logging.debug('Localize face and compute encoding [model=%s]...', model)
   encodings = freg.face_encodings(rgb, freg.face_locations(rgb, model=model))
   logging.info('Localized and computed encodings for %d faces', len(encodings))
   return encodings


def compute_faces_encodings(images_pathes: list[str], model: str) -> list[NDArray]:
   def _list_extended(acc: list, lst: list) -> list:
      acc.extend(lst)
      return acc

   logging.info('Computing encodings for %d images [model=%s]',
               len(images_pathes), model)
   return reduce(_list_extended,
                 map(lambda rgb: localize_faces_and_compute_encodings(rgb, model),
                     map(convert_to_rgb,
                         map(log_imread, images_pathes))), [])


def argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser('encode_faces', description='''
    Localizes faces on images and encodes for further faces recognitions
    ''')

    # Options:
    default_encodings = './memory/faces'
    ap.add_argument('-e', '--encodings', type=Path, default=default_encodings,
        metavar='FILE',
        help=f'file where to store output encodings, default \'{default_encodings}\'')

    default_detection_model = SUPPORTED_DETECTION_MODELS[0]
    ap.add_argument('-f', '--face-detection-model',
        choices=SUPPORTED_DETECTION_MODELS, default=default_detection_model,
        help=f'face detection model to use, default \'{default_detection_model}\'')

    ap.add_argument('-v', '--verbose', action='store_true', default=False,
                    help='be verbosal')

    # Arguments:
    ap.add_argument('images', nargs='*', type=Path, help='input image for encoding')
    return ap


def main() -> int:
    args = argparser().parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    logging.info('Provided %d images', len(args.images))
    try:
        with open(args.encodings, 'wb') as f:
            f.write(pickle.dumps(compute_faces_encodings(args.images,
                                                      args.face_detection_model)))
    except OSError as e:
        logging.error('Failed to dump to file %s', args.encodings)
        logging.error(str(e))
        return e.errno
    except Exception as e:
        logging.critical(f'Unpredicted error occured: {e}', exc_info=e)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())

