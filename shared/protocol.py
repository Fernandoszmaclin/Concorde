
import json
import struct

MAX_MESSAGE_SIZE = 1024 * 1024


def send_message(sock, data):
    payload = json.dumps(data).encode("utf-8")

    if len(payload) > MAX_MESSAGE_SIZE:
        raise ValueError("Mensagem muito grande")

    header = struct.pack("!I", len(payload))
    sock.sendall(header + payload)


def receive_exact(sock, size):
    data = bytearray()

    while len(data) < size:
        chunk = sock.recv(size - len(data))

        if not chunk:
            raise ConnectionError("Conexão encerrada")

        data.extend(chunk)

    return bytes(data)


def receive_message(sock):
    header = receive_exact(sock, 4)
    size = struct.unpack("!I", header)[0]

    if size > MAX_MESSAGE_SIZE:
        raise ValueError("Mensagem muito grande")

    payload = receive_exact(sock, size)
    return json.loads(payload.decode("utf-8"))
