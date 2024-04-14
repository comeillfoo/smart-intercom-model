#!/usr/bin/env python3
import sys
import argparse
import socket
import struct
import pickle
import cv2
from typing import Tuple, Optional
from dataclasses import dataclass, field
from functools import reduce

from contextlib import closing
from pathlib import Path
from numpy.typing import NDArray
from cv2.typing import MatLike

import face_recognition as freg

from tools.encode_faces import SUPPORTED_DETECTION_MODELS
from tools.encode_faces import localize_faces_and_compute_encodings, \
    convert_to_rgb


SUPPORTED_PROTOS = [ 'tcp', 'udp' ]

PROTOS_MAP = {
    'tcp': socket.IPPROTO_TCP,
    'udp': socket.IPPROTO_UDP,
}

LISTEN_BACKLOG = 10


@dataclass
class SBCContext:
    '''Class for storing list of people faces with an access and not,
    and detection model
    '''
    detection_model: str = SUPPORTED_DETECTION_MODELS[0]
    tolerance: float = 0.6 # it's stated as best performance
    granted: list[NDArray] = field(default_factory=list)
    denied: list[NDArray] = field(default_factory=list)


def argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser('sbc', description='''
    Runs SBC that decides whether to unlock the door, based on frames from
    camera.
    ''')

    default_proto = SUPPORTED_PROTOS[0]
    p.add_argument('-p', '--proto', choices=SUPPORTED_PROTOS, default=default_proto,
        help=f'transport protocol to use, default \'{default_proto}\'')

    p.add_argument('-P', '--port', type=int, default=0,
        help='bind port, use 0 for random, default random')

    default_grant = Path('memory/grant')
    p.add_argument('-g', '--grant', default=default_grant, metavar='PATH',
        type=Path, help='path to serialized faces who are allowed to enter, ' \
        f'default \'{default_grant}\'')

    default_deny = Path('memory/deny')
    p.add_argument('-d', '--deny', default=default_deny, metavar='PATH',
        type=Path, help='path to serialized faces who are not allowed to enter, ' \
        f'default \'{default_deny}\'')

    default_detection_model = SUPPORTED_DETECTION_MODELS[0]
    p.add_argument('-f', '--face-detection-model', choices=SUPPORTED_DETECTION_MODELS, default=default_detection_model,
        help=f'face detection model to use, default \'{default_detection_model}\'')

    default_tolerance = 0.6 # it's stated as best performance
    p.add_argument('-t', '--tolerance', type=float, default=default_tolerance,
        help='How much distance between faces to consider it a match. ' \
        f'Lower is more strict, default {default_tolerance}')

    default_host = 'localhost'
    p.add_argument('host', nargs='?', default=default_host,
                   help=f'bind address, default \'{default_host}\'')
    return p


def ask_binary_question(prompt: str) -> bool:
    agree_variants = [ 'y', 'yes' ]
    reject_variants = [ 'n', 'no' ]

    while True:
        try:
            raw_answer = input(prompt + ' (Y/n): ').strip().lower()
            if raw_answer in agree_variants:
                return True
            elif raw_answer in reject_variants:
                return False
        except Exception as e:
            pass # TODO: maybe log this

Box = Tuple[int, int, int, int]

def get_decision_from_user(frame: MatLike, boxes: list[Box]) -> bool:
    ret = False
    try:
        for box in boxes:
            top, right, bottom, left = box
            cv2.rectangle(frame, (left, top), (right, bottom), color=(0, 255, 0))
        cv2.imshow(f'{id(frame)}', frame)
        cv2.waitKey(0)
        ret = ask_binary_question('Let them in?')
        cv2.destroyAllWindows()
    except Exception as e:
        print('Fatal: error while asking user', e)
    return ret


def handle_encoding_cb(known_encodings: list[NDArray], tolerance: float):
    def _mapper(encoding: NDArray) -> bool:
        return reduce(bool.__or__,
                      map(bool, freg.compare_faces(known_encodings, encoding,
                                                   tolerance)),
                      False)
    return _mapper


def reduce_encodings(known_encodings: list[NDArray], encodings: list[NDArray],
                     tolerance: float) -> bool:
    return reduce(bool.__and__,
                  map(handle_encoding_cb(known_encodings, tolerance), encodings),
                  True)


def handle_frame(ctx: SBCContext, frame: MatLike) -> bool:
    rgb_frame = convert_to_rgb(frame)
    encodings = localize_faces_and_compute_encodings(rgb_frame,
                                                     ctx.detection_model)

    is_granted = reduce_encodings(ctx.granted, encodings, ctx.tolerance)
    is_denied = reduce_encodings(ctx.denied, encodings, ctx.tolerance)
    if is_granted == is_denied:
        return get_decision_from_user(frame,
                        freg.face_locations(rgb_frame, model=ctx.detection_model))

    return is_granted and not is_denied


def handle_kbd_int(server_hook):
    def wrapper(ctx: SBCContext, server_sk: socket.socket) -> int:
        try:
            return server_hook(ctx, server_sk)
        except KeyboardInterrupt:
            print('Stopping server...')
        return 0
    return wrapper


def tcp_negotiate(sk: socket.socket) -> Tuple[int, int, int]:
    shape = struct.unpack('NNN', sk.recv(struct.calcsize('NNN'))) # width, height, channels
    if 3 != len(shape):
        raise ValueError
    return shape


def tcp_recv_frame(sk: socket.socket, frame_size: int) -> Tuple[Optional[MatLike], int]:
    data = b''
    payload_len = struct.calcsize('N')
    try:
        while len(data) < payload_len:
            data += sk.recv(payload_len)
        msg_size = struct.unpack('N', data[:payload_len])[0]
        data = data[payload_len:]
        print(msg_size, frame_size)
        while len(data) < msg_size:
            data += sk.recv(frame_size)
        return (pickle.loads(data[:msg_size]), 0)
    except socket.error as serr:
        print(serr)
    return (None, 1)


def tcp_send_answer(sk: socket.socket, answer: bool) -> int:
    ret = 0
    try:
        sk.send(struct.pack('?', answer))
    except socket.error as serr:
        print(serr)
        ret = 1
    return ret


@handle_kbd_int
def tcp_server(ctx: SBCContext, server_sk: socket.socket) -> int:
    server_sk.listen(LISTEN_BACKLOG)
    sk, addr = server_sk.accept()
    print('Connected to camera', addr)
    width, height, channels = tcp_negotiate(sk)
    print('Agreed on %d x %d x %d frames' % (width, height, channels))
    ret = 0
    while True:
        frame, ret = tcp_recv_frame(sk, width * height * channels)
        if ret: break

        print(frame.shape)
        # the decision, whether allow entrance or not, is being made here
        answer = handle_frame(ctx, frame)
        # print('Responding with', answer)
        ret = tcp_send_answer(sk, answer)
        if ret: break
    return ret


@handle_kbd_int
def udp_server(ctx: SBCContext, server_sk: socket.socket) -> int:
    # TODO: udp server
    return 0


SERVER_HOOKS = {
    socket.IPPROTO_TCP: tcp_server,
    socket.IPPROTO_UDP: udp_server,
}


def server_info(family: socket.AddressFamily, sk: socket.socket):
    ipv6_extra_fmt = '; flowinfo: %d; scope id: %d'
    fmt = 'address: %s; port: %d'
    if family == socket.AF_INET6:
        fmt += ipv6_extra_fmt
    print(fmt % sk.getsockname())


def read_faces_encodings(path: Path) -> list[NDArray]:
    try:
        with open(path, 'rb') as f:
            return pickle.loads(f.read())
    except Exception as e:
        return []


def main() -> int:
    ret = 0
    args = argparser().parse_args()

    ctx = SBCContext(args.face_detection_model, args.tolerance,
                     read_faces_encodings(args.grant),
                     read_faces_encodings(args.deny))

    family, type, proto, _, sockaddr = socket.getaddrinfo(args.host, args.port,
        proto=PROTOS_MAP.get(args.proto, socket.IPPROTO_TCP))[0]

    with closing(socket.socket(family, type, proto)) as sk:
        sk.bind(sockaddr)
        sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_info(family, sk)
        ret = SERVER_HOOKS[proto](ctx, sk)
    return ret


if __name__ == '__main__':
    sys.exit(main())
