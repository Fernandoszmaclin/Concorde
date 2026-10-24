"""Servidor UDP: valida sessões e encaminha áudio, sem capturar microfone."""

import secrets
import socket
import threading
import time
from dataclasses import dataclass

from shared.voice_protocol import (
    AUDIO, MAX_DATAGRAM, MAX_PARTICIPANTS, REGISTER, REGISTERED,
    decode_packet, encode_packet,
)


@dataclass
class VoiceSession:
    username: str
    group: str
    peer_ip: str
    token: bytes
    speaker: int
    address: tuple | None = None
    last_seen: float = 0
    budget: float = 20
    budget_time: float = 0


class VoiceRelay:
    def __init__(self, host="127.0.0.1", port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.thread = None
        self.stopped = threading.Event()
        # TCP altera participantes; UDP consulta essas mesmas sessões.
        self.lock = threading.RLock()
        self.sessions = {}
        self.tokens = {}
        self.next_speaker = 1
        self.revision = 0

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((self.host, self.port))
            self.port = self.socket.getsockname()[1]
            self.socket.settimeout(0.2)
        except OSError:
            self.socket.close()
            raise
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()

    def join(self, username, group, peer_ip):
        with self.lock:
            if username in self.sessions:
                raise ValueError("Saia da chamada atual antes de entrar em outra")
            if sum(s.group == group for s in self.sessions.values()) >= MAX_PARTICIPANTS:
                raise ValueError(f"Chamada lotada: máximo de {MAX_PARTICIPANTS} pessoas")
            # O token associa o UDP à sessão que já foi aceita pelo TCP.
            session = VoiceSession(
                username, group, peer_ip, secrets.token_bytes(16), self.next_speaker,
                budget_time=time.monotonic(),
            )
            self.next_speaker += 1
            self.sessions[username] = session
            self.tokens[session.token] = session
            self.revision += 1
            return session

    def leave(self, username, group=None):
        with self.lock:
            session = self.sessions.get(username)
            if session is None or (group is not None and session.group != group):
                return None
            del self.sessions[username]
            del self.tokens[session.token]
            self.revision += 1
            return session.group

    def participants(self, group):
        return self.snapshot(group)["participants"]

    def snapshot(self, group):
        with self.lock:
            participants = [
                {"username": s.username, "speaker": s.speaker}
                for s in self.sessions.values() if s.group == group
            ]
            # Threads TCP podem entregar listas em ordem diferente da criação.
            # A revisão permite ao cliente ignorar uma lista que ficou antiga.
            return {"participants": participants, "revision": self.revision}

    def _handle_datagram(self, data, address):
        try:
            packet = decode_packet(data)
        except ValueError:
            return  # Um pacote inválido não pode derrubar o receptor.

        now = time.monotonic()
        with self.lock:
            session = self.tokens.get(packet.token)
            if session is None or address[0] != session.peer_ip:
                return

            # Limite por sessão: 50 blocos/s são esperados; toleramos pequenas rajadas.
            session.budget = min(20, session.budget + (now - session.budget_time) * 70)
            session.budget_time = now
            if session.budget < 1:
                return
            session.budget -= 1

            if packet.kind == REGISTER:
                # O endereço UDP vem do próprio datagrama, não de um IP informado
                # pelo cliente. Depois do registro, a porta permanece vinculada.
                if session.address is not None and session.address != address:
                    return
                session.address = address
                session.last_seen = now
                self._send(encode_packet(REGISTERED, session.token), address)
                return

            if packet.kind != AUDIO or session.address != address:
                return
            session.last_seen = now

            for target in self.sessions.values():
                if (target.group != session.group or target is session
                        or target.address is None or now - target.last_seen > 5):
                    continue
                # O servidor define o emissor. Nunca confia no ID enviado pelo cliente.
                # Cada destinatário recebe seu próprio token, sem conhecer o dos demais.
                forwarded = encode_packet(
                    AUDIO, target.token, session.speaker, packet.sequence, packet.payload
                )
                self._send(forwarded, target.address)

    def _send(self, data, address):
        try:
            self.socket.sendto(data, address)
        except OSError:
            pass  # Perda pontual é tolerada; a chamada não espera retransmissão.

    def _receive_loop(self):
        while not self.stopped.is_set():
            try:
                # Um byte extra permite identificar e descartar pacotes grandes.
                data, address = self.socket.recvfrom(MAX_DATAGRAM + 1)
            except socket.timeout:
                continue
            except OSError:
                if self.stopped.is_set():
                    break
                continue
            self._handle_datagram(data, address)

    def close(self):
        self.stopped.set()
        if self.socket is not None:
            self.socket.close()
        if self.thread is not None:
            self.thread.join(timeout=1)
