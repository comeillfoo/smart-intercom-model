#!/usr/bin/env python3
import sys
import cv2

WINDOW_NAME='cam1'

def main() -> int:
    ret = 0
    cam = cv2.VideoCapture(0)
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    while True:
        camret, frame = cam.read()
        if not camret:
            print('failed to grab frame')
            ret = 1
            break

        cv2.imshow(WINDOW_NAME, frame)
        k = cv2.waitKey(1)
        if k % 256 == 27: # ESC
            print('ESC pressed, exitting')
            break

    cv2.destroyAllWindows()
    cam.release()
    return ret


if __name__ == '__main__':
    sys.exit(main())
