#!/usr/bin/env python3
import sys
import argparse
import socket
import pickle
import struct
import cv2
from contextlib import closing


SUPPORTED_PROTOS = [ 'tcp', 'udp' ] # TODO: rtsp

PROTOS_MAP = {
    'tcp': socket.IPPROTO_TCP,
    'udp': socket.IPPROTO_UDP,
}


def argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser('camera', description='''
    Runs camera that connects to SBC and sends frames from WebCam for receiving
    the decision about door unlocking.
    ''')

    default_proto = 'tcp'
    p.add_argument('-p', '--proto', choices=SUPPORTED_PROTOS, default=default_proto,
        help=f'belect the transfer protocol, default \'{default_proto}\'')

    p.add_argument('-P', '--port', type=int, required=True, help='connect port')

    default_host = 'localhost'
    p.add_argument('host', nargs='?', default=default_host,
                   help=f'connect address, default \'{default_host}\'')
    return p


def tcp_negotiate(cam, sk: socket.socket) -> int:
    test_ret, test_frame = cam.read()
    if not test_ret: return 1
    sk.sendall(struct.pack('NNN', *test_frame.shape))
    return 0


def handle_kbd_int(client):
    def wrapper(cam, sk: socket.socket, sockaddr) -> int:
        try:
            return client(cam, sk, sockaddr)
        except KeyboardInterrupt:
            print('Stopping client...')
        return 0
    return wrapper


@handle_kbd_int
def tcp_client(cam, sk: socket.socket, sockaddr) -> int:
    sk.connect(sockaddr)
    ret = tcp_negotiate(cam, sk)
    if ret: return ret
    while True:
        pass
        # camret, frame = cam.read()
        # if not camret:
        #     print('failed to grab frame')
        #     ret = 1
        #     break
        # data = pickle.dumps(frame)
        # sk.sendall(struct.pack('H', len(data)) + data)

    return ret


def udp_client(cam, sk: socket.socket, sockaddr) -> int:
    return 0


SERVER_HOOKS = {
    socket.IPPROTO_TCP: tcp_client,
    socket.IPPROTO_UDP: udp_client,
}


def main() -> int:
    ret = 0
    args = argparser().parse_args()

    cam = cv2.VideoCapture(0)

    family, type, proto, _, sockaddr = socket.getaddrinfo(args.host, args.port,
        proto=PROTOS_MAP.get(args.proto, socket.IPPROTO_TCP))[0]
    with closing(socket.socket(family, type, proto)) as sk:
        ret = SERVER_HOOKS[proto](cam, sk, sockaddr)

    cam.release()
    return ret


if __name__ == '__main__':
    sys.exit(main())
