"""Contrato UDP compartilhado pelos clientes e pelo servidor de voz."""

import struct
from dataclasses import dataclass


# Todos usam o mesmo formato: 320 amostras de 16 bits = 640 bytes a cada 20 ms.
SAMPLE_RATE = 16_000
CHANNELS = 1
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2
SILENCE = bytes(FRAME_BYTES)
DEFAULT_VOICE_PORT = 5001
MAX_PARTICIPANTS = 8
SEQUENCE_MASK = 0xFFFFFFFF

REGISTER = 1
REGISTERED = 2
AUDIO = 3

# ! = ordem de rede. Cabeçalho: versão, tipo, token, emissor, sequência.
# O PCM usa little-endian explicitamente, independentemente do computador.
MAGIC = b"D2V1"
HEADER = struct.Struct("!4sB16sII")
MAX_DATAGRAM = HEADER.size + FRAME_BYTES


@dataclass(frozen=True)
class VoicePacket:
    kind: int
    token: bytes
    speaker: int = 0
    sequence: int = 0
    payload: bytes = b""


def encode_packet(kind, token, speaker=0, sequence=0, payload=b""):
    if len(token) != 16:
        raise ValueError("Token de voz deve ter 16 bytes")
    if kind not in (REGISTER, REGISTERED, AUDIO):
        raise ValueError("Tipo de pacote de voz inválido")
    expected = FRAME_BYTES if kind == AUDIO else 0
    if len(payload) != expected:
        raise ValueError("Tamanho de áudio inválido")
    return HEADER.pack(MAGIC, kind, token, speaker, sequence) + payload


def decode_packet(data):
    if not HEADER.size <= len(data) <= MAX_DATAGRAM:
        raise ValueError("Tamanho de datagrama inválido")
    magic, kind, token, speaker, sequence = HEADER.unpack_from(data)
    if magic != MAGIC or kind not in (REGISTER, REGISTERED, AUDIO):
        raise ValueError("Cabeçalho de voz inválido")
    payload = data[HEADER.size:]
    if len(payload) != (FRAME_BYTES if kind == AUDIO else 0):
        raise ValueError("Bloco PCM incompleto ou dados extras")
    return VoicePacket(kind, token, speaker, sequence, payload)


def sequence_distance(sequence, reference):
    """Diferença com sinal, inclusive quando o contador de 32 bits dá a volta."""
    return ((sequence - reference + 0x80000000) & SEQUENCE_MASK) - 0x80000000
