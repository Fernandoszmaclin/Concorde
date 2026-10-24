"""Testes reproduzíveis sem microfone: rede real em loopback e PCM sintético."""

import socket
import threading
import time
import unittest
from functools import partial
from unittest.mock import patch

from client.tcp_client import TCPClient
from client.voice_buffer import PCM, VoiceMixer
from client.voice_client import VoiceClient
from server import server_test as chat
from server.voice_server import VoiceRelay
from shared.protocol import receive_message, send_message
from shared.voice_protocol import (
    AUDIO, FRAME_BYTES, FRAME_SAMPLES, MAX_DATAGRAM, MAX_PARTICIPANTS,
    REGISTER, REGISTERED, SEQUENCE_MASK, SILENCE, decode_packet,
    encode_packet, sequence_distance,
)


TOKEN = bytes(range(16))


def pcm(value):
    return PCM.pack(*([value] * FRAME_SAMPLES))


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self):
        packet = decode_packet(encode_packet(AUDIO, TOKEN, 7, 12, pcm(123)))
        self.assertEqual((packet.speaker, packet.sequence), (7, 12))
        self.assertEqual(packet.payload, pcm(123))
        self.assertEqual(MAX_DATAGRAM, 669)

    def test_rejects_malformed_packets(self):
        valid = encode_packet(AUDIO, TOKEN, payload=SILENCE)
        for data in (b"", valid[:-1], valid + b"x", b"FAIL" + valid[4:],
                     encode_packet(REGISTER, TOKEN) + b"x"):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                decode_packet(data)

    def test_counter_wrap(self):
        self.assertEqual(sequence_distance(0, SEQUENCE_MASK), 1)
        self.assertEqual(sequence_distance(SEQUENCE_MASK, 0), -1)


class MixerTests(unittest.TestCase):
    def setUp(self):
        self.mixer = VoiceMixer()
        self.mixer.set_participants([1, 2])

    def test_jitter_reordering_and_loss(self):
        self.mixer.add(1, 0, pcm(100), now=0)
        self.mixer.add(1, 2, pcm(300), now=0.02)
        self.mixer.add(1, 1, pcm(200), now=0.03)
        self.assertEqual(self.mixer.render(now=0.04), SILENCE)
        self.assertEqual(self.mixer.render(now=0.061), pcm(100))
        self.assertEqual(self.mixer.render(now=0.081), pcm(200))
        self.assertEqual(self.mixer.render(now=0.101), pcm(300))
        self.assertEqual(self.mixer.render(now=0.121), SILENCE)
        # Retransmissão atrasada não deve reaparecer no áudio atual.
        self.mixer.add(1, 1, pcm(999), now=0.13)
        self.assertEqual(self.mixer.render(now=0.141), SILENCE)

    def test_multiple_speakers_and_clipping(self):
        self.mixer.add(1, 0, pcm(25_000), now=0)
        self.mixer.add(2, 0, pcm(25_000), now=0)
        self.assertEqual(self.mixer.render(now=0.061), pcm(32767))
        self.mixer.add(1, 1, pcm(-25_000), now=0.07)
        self.mixer.add(2, 1, pcm(-25_000), now=0.07)
        self.assertEqual(self.mixer.render(now=0.081), pcm(-32768))

    def test_participant_removal_and_unknown_sender(self):
        self.mixer.add(9, 0, pcm(999), now=0)
        self.assertEqual(self.mixer.render(now=0.061), SILENCE)
        self.mixer.add(1, 0, pcm(100), now=0)
        self.mixer.set_participants([2])
        self.assertEqual(self.mixer.render(now=0.061), SILENCE)

    def test_backlog_is_bounded_and_wrap_works(self):
        self.mixer.add(1, SEQUENCE_MASK, pcm(100), now=0)
        self.mixer.add(1, 0, pcm(200), now=0.01)
        self.assertEqual(self.mixer.render(now=0.061), pcm(100))
        self.assertEqual(self.mixer.render(now=0.081), pcm(200))
        for sequence in range(1, 200):
            self.mixer.add(1, sequence, pcm(300), now=0.1)
        self.assertLessEqual(len(self.mixer.speakers[1].packets), 10)
        self.assertEqual(self.mixer.render(now=0.17), pcm(300))


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.relay = VoiceRelay(port=0)
        self.relay.start()
        self.addCleanup(self.relay.close)

    def register(self, username, group):
        session = self.relay.join(username, group, "127.0.0.1")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sock.close)
        sock.connect(("127.0.0.1", self.relay.port))
        sock.settimeout(0.15)
        sock.send(encode_packet(REGISTER, session.token))
        self.assertEqual(decode_packet(sock.recv(MAX_DATAGRAM)).kind, REGISTERED)
        return session, sock

    def test_group_routing_no_echo_and_token_validation(self):
        alice, a = self.register("alice", "redes")
        bob, b = self.register("bob", "redes")
        carol, c = self.register("carol", "redes")
        other, d = self.register("outro", "outro-grupo")
        a.send(encode_packet(AUDIO, alice.token, speaker=999, sequence=8, payload=pcm(123)))
        for sock, target in ((b, bob), (c, carol)):
            packet = decode_packet(sock.recv(MAX_DATAGRAM))
            self.assertEqual(packet.token, target.token)
            self.assertEqual(packet.speaker, alice.speaker)
            self.assertEqual(packet.payload, pcm(123))
        for sock in (a, d):
            with self.assertRaises(socket.timeout):
                sock.recv(MAX_DATAGRAM)

        a.send(encode_packet(AUDIO, b"x" * 16, payload=SILENCE))
        with self.assertRaises(socket.timeout):
            b.recv(MAX_DATAGRAM)
        self.relay.leave("alice")
        a.send(encode_packet(AUDIO, alice.token, payload=SILENCE))
        with self.assertRaises(socket.timeout):
            b.recv(MAX_DATAGRAM)

    def test_unregistered_and_wrong_port_cannot_send(self):
        bob, b = self.register("bob", "redes")
        alice = self.relay.join("alice", "redes", "127.0.0.1")
        wrong = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(wrong.close)
        wrong.connect(("127.0.0.1", self.relay.port))
        wrong.send(encode_packet(AUDIO, alice.token, payload=SILENCE))
        with self.assertRaises(socket.timeout):
            b.recv(MAX_DATAGRAM)

        # Mesmo token com porta diferente não pode substituir registro já feito.
        alice2, a = self.register("alice2", "redes")
        wrong.send(encode_packet(REGISTER, alice2.token))
        wrong.send(encode_packet(AUDIO, alice2.token, payload=SILENCE))
        with self.assertRaises(socket.timeout):
            b.recv(MAX_DATAGRAM)

    def test_group_capacity_and_duplicate_join(self):
        for index in range(MAX_PARTICIPANTS):
            self.relay.join(str(index), "redes", "127.0.0.1")
        with self.assertRaises(ValueError):
            self.relay.join("extra", "redes", "127.0.0.1")
        with self.assertRaises(ValueError):
            self.relay.join("0", "outro", "127.0.0.1")


class FakeAudio:
    """Simula relógio do dispositivo, sem abrir microfone nem tocar som."""
    def __init__(self, *_):
        self.aborted = threading.Event()
        self.closed = False
        self.blocks = []

    def start(self):
        pass

    def read(self):
        self.aborted.wait(0.02)
        return pcm(100)

    def write(self, block):
        self.blocks.append(block)
        self.aborted.wait(0.02)

    def abort(self):
        self.aborted.set()

    def close(self):
        self.closed = True


class AudioClientTests(unittest.TestCase):
    def test_old_participant_snapshot_is_ignored(self):
        voice = VoiceClient("127.0.0.1", 5001, TOKEN.hex(), "redes")
        self.assertTrue(voice.set_participants([{"speaker": 1}], revision=5))
        self.assertFalse(voice.set_participants([{"speaker": 2}], revision=4))
        self.assertEqual(voice.mixer.allowed, {1})

    def test_two_clients_audio_mute_and_cleanup(self):
        relay = VoiceRelay(port=0)
        relay.start()
        self.addCleanup(relay.close)
        clients = []
        for name in ("alice", "bob"):
            session = relay.join(name, "redes", "127.0.0.1")
            voice = VoiceClient("127.0.0.1", relay.port, session.token.hex(), "redes",
                                audio_factory=FakeAudio)
            voice.start()
            self.addCleanup(voice.stop)
            clients.append(voice)
        for voice in clients:
            voice.set_participants(relay.participants("redes"))

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if all(pcm(100) in voice.audio.blocks for voice in clients):
                break
            threading.Event().wait(0.02)
        self.assertTrue(all(pcm(100) in voice.audio.blocks for voice in clients))
        clients[0].set_muted(True)
        # Depois da fila e do jitter buffer, Bob deve ouvir apenas silêncio.
        threading.Event().wait(0.4)
        self.assertTrue(all(block == SILENCE for block in clients[1].audio.blocks[-5:]))
        for voice in clients:
            voice.stop()
            self.assertTrue(voice.audio.closed)
            self.assertFalse(any(worker.is_alive() for worker in voice.workers))
            self.assertFalse(voice.supervisor.is_alive())
            self.assertIsNone(voice.last_error)


class ChatIntegrationTests(unittest.TestCase):
    def setUp(self):
        # handle_client é o mesmo caminho utilizado pelo servidor executável.
        chat.clients.clear()
        chat.groups.clear()
        chat.voice_relay = VoiceRelay(port=0)
        chat.voice_relay.start()
        self.relay = chat.voice_relay
        self.sockets = []
        self.threads = []
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()

    def tearDown(self):
        for sock in self.sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        for thread in self.threads:
            thread.join(timeout=2)
        self.listener.close()
        self.relay.close()

    def connect(self, username):
        client = socket.create_connection(self.listener.getsockname(), timeout=2)
        self.sockets.append(client)
        conn, address = self.listener.accept()
        thread = threading.Thread(target=chat.handle_client, args=(conn, address), daemon=True)
        self.threads.append(thread)
        thread.start()
        send_message(client, {"type": "LOGIN", "username": username})
        return client

    def event(self, sock, kind):
        # Ignora broadcasts intercalados, exatamente como um cliente real precisa fazer.
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            data = receive_message(sock)
            if data.get("type") == kind:
                return data
        self.fail(f"Evento não recebido: {kind}")

    def wait_for(self, predicate, seconds=3):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            threading.Event().wait(0.02)
        self.fail("Estado esperado não alcançado")

    def connect_app(self, username):
        client = TCPClient(*self.listener.getsockname())
        client.connect()
        conn, address = self.listener.accept()
        thread = threading.Thread(target=chat.handle_client, args=(conn, address), daemon=True)
        self.threads.append(thread)
        thread.start()
        self.assertEqual(client.login(username)["type"], "LOGIN_OK")
        self.addCleanup(client.disconnect)
        return client

    def test_real_tcp_client_controls_voice_and_rejoins(self):
        with patch("client.tcp_client.VoiceClient", partial(VoiceClient, audio_factory=FakeAudio)):
            alice = self.connect_app("alice")
            bob = self.connect_app("bob")
            alice.create_group("redes")
            self.wait_for(lambda: "redes" in chat.groups)
            bob.join_group("redes")
            self.wait_for(lambda: "bob" in chat.groups["redes"])
            alice.join_voice("redes")
            bob.join_voice("redes")
            self.wait_for(lambda: alice.voice is not None and bob.voice is not None)
            self.wait_for(lambda: pcm(100) in alice.voice.audio.blocks
                          and pcm(100) in bob.voice.audio.blocks)
            alice.toggle_mute()
            self.assertTrue(alice.voice.muted.is_set())
            old_voice = alice.voice
            alice.leave_voice()
            self.wait_for(lambda: not alice.voice_leaving)
            self.assertTrue(old_voice.audio.closed)
            self.assertNotIn("alice", self.relay.sessions)
            alice.join_voice("redes")
            self.wait_for(lambda: alice.voice is not None)
            self.assertNotEqual(alice.voice.token, old_voice.token)
            bob.disconnect()
            self.wait_for(lambda: "bob" not in self.relay.sessions)
            self.assertIsNone(bob.voice)
            alice.disconnect()

    def test_chat_voice_membership_and_disconnect(self):
        alice = self.connect("alice")
        self.event(alice, "LOGIN_OK")
        bob = self.connect("bob")
        self.event(bob, "LOGIN_OK")
        send_message(alice, {"type": "GROUP_CREATE", "group": "redes"})
        self.event(alice, "GROUP_EVENT")
        send_message(bob, {"type": "VOICE_JOIN", "group": "redes"})
        self.assertIn("grupo de texto", self.event(bob, "VOICE_ERROR")["message"])
        send_message(bob, {"type": "GROUP_JOIN", "group": "redes"})
        self.event(bob, "GROUP_EVENT")
        tokens = []
        for sock in (alice, bob):
            send_message(sock, {"type": "VOICE_JOIN", "group": "redes"})
            tokens.append(self.event(sock, "VOICE_JOINED")["token"])
        self.assertNotEqual(*tokens)
        event = self.event(bob, "VOICE_PARTICIPANTS")
        self.assertEqual(len(event["participants"]), 2)

        # Texto continua funcionando enquanto a sessão de voz existe.
        send_message(alice, {"type": "GROUP_MESSAGE", "group": "redes", "message": "oi"})
        self.assertEqual(self.event(bob, "GROUP_MESSAGE_RECEIVED")["message"], "oi")
        send_message(bob, {"type": "GROUP_LEAVE", "group": "redes"})
        self.event(bob, "VOICE_LEFT")
        self.event(bob, "GROUP_EVENT")
        self.assertNotIn("bob", self.relay.sessions)

        alice.shutdown(socket.SHUT_RDWR)
        alice.close()
        self.threads[0].join(timeout=2)
        self.assertNotIn("alice", self.relay.sessions)

    def test_duplicate_login_preserves_original(self):
        original = self.connect("alice")
        self.event(original, "LOGIN_OK")
        duplicate = self.connect("alice")
        self.assertIn("conectado", self.event(duplicate, "ERROR")["message"])
        self.threads[1].join(timeout=2)
        send_message(original, {"type": "GROUP_CREATE", "group": "redes"})
        self.event(original, "GROUP_EVENT")
        self.assertIn("alice", chat.clients)


if __name__ == "__main__":
    unittest.main()
