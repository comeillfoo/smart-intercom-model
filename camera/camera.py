#!/usr/bin/env python3
import sys
import argparse
import socket
import pickle
import struct
import cv2
import time
from contextlib import closing
from typing import Tuple
import threading

from lock import DoorLock

PROTOS_KEY_VALUES = [
    ('tcp', socket.IPPROTO_TCP),
    ('udp', socket.IPPROTO_UDP)
]

SUPPORTED_PROTOS = list(map(lambda pair: pair[0], PROTOS_KEY_VALUES))

PROTOS_MAP = dict(PROTOS_KEY_VALUES)


def argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser('camera', description='''
    Runs camera that connects to SBC and sends frames from WebCam for receiving
    the decision about door unlocking.
    ''')

    default_proto = 'tcp'
    p.add_argument('-p', '--proto', choices=SUPPORTED_PROTOS, default=default_proto,
        help=f'select the transfer protocol, default \'{default_proto}\'')

    p.add_argument('-P', '--port', type=int, required=True, help='connect port')

    default_delay = 3.0 # seconds
    p.add_argument('-d', '--delay', type=float, default=default_delay,
        help=f'delay (seconds) between frame sends, default {default_delay}')

    default_host = 'localhost'
    p.add_argument('host', nargs='?', default=default_host,
                   help=f'connect address, default \'{default_host}\'')
    return p


def tcp_negotiate(cam: cv2.VideoCapture, sk: socket.socket) -> int:
    test_ret, test_frame = cam.read()
    if not test_ret: return 1
    sk.sendall(struct.pack('NNN', *test_frame.shape))
    return 0


def handle_kbd_int(client_hook):
    def wrapper(cam: cv2.VideoCapture, door: DoorLock, sk: socket.socket,
                sockaddr, delay: float = 3.0) -> int:
        try:
            return client_hook(cam, door, sk, sockaddr, delay)
        except KeyboardInterrupt:
            print('Stopping client...')
        return 0
    return wrapper


def tcp_send_frame(cam: cv2.VideoCapture, sk: socket.socket) -> int:
    camret, frame = cam.read()
    if not camret:
        print('Failed to capture frame')
        return 1
    data = pickle.dumps(frame)
    try:
        sk.sendall(struct.pack('N', len(data)) + data)
    except socket.error as serr:
        print(serr)
        return 1
    return 0


def tcp_recv_answer(sk: socket.socket) -> Tuple[bool, int]:
    answer, ret = False, 0
    try:
        answer = struct.unpack('?', sk.recv(1))
    except socket.error as serr:
        print(serr)
        ret = 1
    return (answer, ret)


@handle_kbd_int
def tcp_client(cam: cv2.VideoCapture, door: DoorLock, sk: socket.socket, sockaddr,
               delay: float = 3.0) -> int:
    sk.connect(sockaddr)
    ret = tcp_negotiate(cam, sk)
    if ret: return ret
    while True:
        ret = tcp_send_frame(cam, sk)
        if ret: break
        time.sleep(delay)
        should_door_unlock, ret = tcp_recv_answer(sk)
        if ret: break
        if should_door_unlock:
            threading.Thread(target=DoorLock.unlock_lock, args=[door]).start()
    return ret


def udp_client(cam: cv2.VideoCapture, door: DoorLock, sk: socket.socket,
               sockaddr, delay: float = 3.0) -> int:
    # TODO: udp client
    return 0


CLIENT_HOOKS = {
    socket.IPPROTO_TCP: tcp_client,
    socket.IPPROTO_UDP: udp_client,
}


def main() -> int:
    ret = 0
    args = argparser().parse_args()

    cam = cv2.VideoCapture(0)
    door = DoorLock()

    family, type, proto, _, sockaddr = socket.getaddrinfo(args.host, args.port,
        proto=PROTOS_MAP.get(args.proto, socket.IPPROTO_TCP))[0]

    with closing(socket.socket(family, type, proto)) as sk:
        ret = CLIENT_HOOKS[proto](cam, door, sk, sockaddr, args.delay)

    cam.release()
    return ret


if __name__ == '__main__':
    sys.exit(main())
