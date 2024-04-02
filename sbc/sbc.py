#!/usr/bin/env python3
import sys
import argparse
import socket
import struct
import pickle
from contextlib import closing
from pathlib import Path
from numpy.typing import NDArray

from tools.encode_faces import SUPPORTED_DETECTION_MODELS


SUPPORTED_PROTOS = [ 'tcp', 'udp' ]

PROTOS_MAP = {
    'tcp': socket.IPPROTO_TCP,
    'udp': socket.IPPROTO_UDP,
}

LISTEN_BACKLOG = 10


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


    default_host = 'localhost'
    p.add_argument('host', nargs='?', default=default_host,
                   help=f'bind address, default \'{default_host}\'')
    return p


def tcp_negotiate(sk: socket.socket) -> tuple[int, int, int]:
    shape = struct.unpack('NNN', sk.recv(struct.calcsize('NNN'))) # width, height, channels
    if 3 != len(shape):
        raise ValueError
    return shape


def handle_kbd_int(server):
    def wrapper(server_sk: socket.socket) -> int:
        try:
            return server(server_sk)
        except KeyboardInterrupt:
            print('Stopping server...')
        return 0
    return wrapper


def tcp_recv_frame(sk: socket.socket, frame_size: int):
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
def tcp_server(server_sk: socket.socket) -> int:
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
        if ret: break
        ret = tcp_send_answer(sk, True)
        if ret: break
    return ret


def udp_server(server_sk: socket.socket) -> int:
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

    granted = read_faces_encodings(args.grant)
    denied = read_faces_encodings(args.deny)

    family, type, proto, _, sockaddr = socket.getaddrinfo(args.host, args.port,
        proto=PROTOS_MAP.get(args.proto, socket.IPPROTO_TCP))[0]

    with closing(socket.socket(family, type, proto)) as sk:
        sk.bind(sockaddr)
        sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_info(family, sk)
        ret = SERVER_HOOKS[proto](sk)
    return ret


if __name__ == '__main__':
    sys.exit(main())
