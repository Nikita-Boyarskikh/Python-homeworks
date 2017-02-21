#!/usr/bin/python3
"""
Обрабатываем/отправляем сообщения согласно протоколу:
сообщения разделены нулевым байтом \0.
"""
import select
import socket
import sys
import re

HOST = "127.0.0.1"
PORT = 9999
clients = {}
alias = re.compile(r'alias (\d+\.\d+\.\d+\.\d+):(\d+)=(\w+)')

START = b'>'
SEP = b"\0"


class Client:

    def __init__(self, sock):
        self.sock = sock
        self.peername = sock.getpeername()
        self._out_stream = bytes()
        self._accumulated_data = bytes()

    def send(self, message):
        self._out_stream += START + message + SEP

    def recv(self):
        data = self.sock.recv(1)
        if not data:
            self.sock.close()
            return None

        self._accumulated_data += data

        messages = []

        while True:
            if SEP in self._accumulated_data:
                msg, rest = self._accumulated_data.split(SEP, 1)
                self._accumulated_data = rest
                messages.append(msg)
            else:
                break

        return messages

    def flush(self):
        sent = self.sock.send(self._out_stream)
        self._out_stream = self._out_stream[sent:]
        return len(self._out_stream) == 0


def broadcast(poll, message):
    for client in clients.values():
        client.send(message)
        poll.register(client.sock, select.POLLOUT)

def execute(command):
    if command == 'count':
        print('>Number of conected clients: {}'.format(len(clients)))
    elif command == 'exit' or command == 'q' or command == 'quit':
        exit(0)
    elif re.match(alias, command):
        a=re.search(alias, command).groups()
        print('{} -> {}:{}'.format(a[2],a[0],a[1]))
    else:
        print('>Unknown command')

def main():
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind((HOST, PORT))
    listen_sock.listen(5)

    poll = select.poll()
    poll.register(listen_sock, select.POLLIN)
    poll.register(sys.stdin, select.POLLIN)

    print('Server listening on {}:{}'.format(HOST, PORT))    

    while True:

        for fd, event in poll.poll():

            # сокет с ошибкой или соединение было закрыто
            if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                poll.unregister(fd)
                client = clients[fd]
                print('Client {} disconnected'.format(clients[fd].peername))
                del clients[fd]

            # слушающий сокет
            elif fd == listen_sock.fileno():
                client_sock, addr = listen_sock.accept()
                client_sock.setblocking(0)
                fd = client_sock.fileno()
                clients[fd] = Client(client_sock)
                poll.register(fd, select.POLLIN)
                print('Connection from {}'.format(addr))

            # администратор написал команду
            elif fd == 0:
                command = input()
                execute(command)

            # новые данные от клиента
            elif event & select.POLLIN:
                client = clients[fd]
                messages = client.recv()
                if messages:
                    print('From {}:'.format(client.peername))
                    for message in messages:
                        print('>' + message.decode())
                        broadcast(poll, message)

            # сокет клиента готов к записи
            elif event & select.POLLOUT:
                client = clients[fd]
                is_empty = client.flush()
                if is_empty:
                    poll.modify(client.sock, select.POLLIN)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
