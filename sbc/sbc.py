#!/usr/bin/env python3
import sys
import argparse
import socket
import struct
from contextlib import closing


SUPPORTED_PROTOS = [ 'tcp', 'udp' ] # TODO: rtsp

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

    default_proto = 'tcp'
    p.add_argument('-p', '--proto', choices=SUPPORTED_PROTOS, default=default_proto,
        help=f'belect the transfer protocol, default \'{default_proto}\'')

    p.add_argument('-P', '--port', type=int, default=0,
        help='bind port, use 0 for random')

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


@handle_kbd_int
def tcp_server(server_sk: socket.socket) -> int:
    server_sk.listen(LISTEN_BACKLOG)
    sk, addr = server_sk.accept()
    print('Agreed on ', *tcp_negotiate(sk))
    while True:
        pass
    return 0


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


def main() -> int:
    ret = 0
    args = argparser().parse_args()

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
