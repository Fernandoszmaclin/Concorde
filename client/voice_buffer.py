"""Reordenação limitada de pacotes e mistura PCM, sem depender de hardware."""

import struct
import threading
import time

from shared.voice_protocol import (
    FRAME_BYTES, FRAME_MS, FRAME_SAMPLES, MAX_PARTICIPANTS,
    SEQUENCE_MASK, SILENCE, sequence_distance,
)


PCM = struct.Struct(f"<{FRAME_SAMPLES}h")


class SpeakerBuffer:
    def __init__(self, sequence, now):
        self.expected = sequence
        self.ready_at = now + 3 * FRAME_MS / 1000  # 60 ms para absorver jitter.
        self.last_received = now
        self.packets = {}

    def add(self, sequence, payload, now):
        distance = sequence_distance(sequence, self.expected)
        if distance < 0:
            return  # Pacote atrasado: seu instante de reprodução já passou.
        if distance >= 10:
            # Se houver atraso acumulado, voltamos ao áudio recente (fila limitada).
            self.expected = sequence
            self.packets.clear()
            self.ready_at = now + 3 * FRAME_MS / 1000
        self.packets.setdefault(sequence, payload)
        self.last_received = now

    def pop(self, now):
        if now < self.ready_at:
            return SILENCE
        payload = self.packets.pop(self.expected, SILENCE)
        self.expected = (self.expected + 1) & SEQUENCE_MASK
        # Sem retransmissão: uma lacuna vira 20 ms de silêncio, não uma espera.
        return payload


class VoiceMixer:
    def __init__(self):
        self.lock = threading.Lock()
        self.allowed = set()
        self.speakers = {}

    def set_participants(self, speakers):
        with self.lock:
            self.allowed = set(speakers)
            self.speakers = {
                key: value for key, value in self.speakers.items() if key in self.allowed
            }

    def add(self, speaker, sequence, payload, now=None):
        if len(payload) != FRAME_BYTES:
            return
        now = time.monotonic() if now is None else now
        with self.lock:
            if speaker not in self.allowed:
                return
            state = self.speakers.get(speaker)
            if state is None or now - state.last_received > 1:
                if state is None and len(self.speakers) >= MAX_PARTICIPANTS:
                    return
                state = SpeakerBuffer(sequence, now)
                self.speakers[speaker] = state
            state.add(sequence, payload, now)

    def render(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            self.speakers = {
                key: value for key, value in self.speakers.items()
                if now - value.last_received <= 1
            }
            blocks = [state.pop(now) for state in self.speakers.values()]

        if not blocks:
            return SILENCE
        # Somamos em inteiros Python (sem overflow), depois limitamos a int16.
        mixed = [0] * FRAME_SAMPLES
        for block in blocks:
            for index, sample in enumerate(PCM.unpack(block)):
                mixed[index] += sample
        return PCM.pack(*(max(-32768, min(32767, sample)) for sample in mixed))
