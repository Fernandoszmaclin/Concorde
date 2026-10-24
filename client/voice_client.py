"""Captura, envio, recepção e reprodução de voz em tarefas independentes."""

import socket
import sys
import threading
import time
from array import array

from client.voice_buffer import VoiceMixer
from shared.voice_protocol import (
    AUDIO, CHANNELS, FRAME_SAMPLES, MAX_DATAGRAM, REGISTER, REGISTERED,
    SAMPLE_RATE, SEQUENCE_MASK, SILENCE, decode_packet, encode_packet,
)


def load_sounddevice():
    # Importação tardia: mensagens de texto e testes de rede funcionam sem áudio.
    try:
        import sounddevice
    except (ImportError, OSError) as error:
        raise RuntimeError(
            "Áudio indisponível. Instale: python -m pip install -r requirements.txt"
        ) from error
    return sounddevice


def list_audio_devices():
    return str(load_sounddevice().query_devices())


def native_pcm(data):
    """PortAudio usa ordem nativa; o protocolo usa int16 little-endian."""
    data = bytes(data)
    if sys.byteorder == "little":
        return data
    samples = array("h")
    samples.frombytes(data)
    samples.byteswap()
    return samples.tobytes()


def open_audio_stream(sd, kind, requested_device):
    """Prefere WASAPI compartilhado no Windows e respeita IDs explícitos."""
    candidates = []
    if requested_device is None and sys.platform == "win32":
        for api in sd.query_hostapis():
            if api["name"] == "Windows WASAPI":
                device = api[f"default_{kind}_device"]
                if device >= 0:
                    candidates.append(device)
    # Não trocamos silenciosamente um microfone escolhido pelo usuário.
    candidates.append(requested_device)
    factory = sd.RawInputStream if kind == "input" else sd.RawOutputStream
    label = "microfone" if kind == "input" else "saída de áudio"
    errors = []
    tried = set()
    for device in candidates:
        try:
            info = sd.query_devices(device, kind)
            if info["index"] in tried:
                continue
            tried.add(info["index"])
            if info[f"max_{kind}_channels"] < CHANNELS:
                errors.append(f"{info['name']}: não possui canais de {kind}")
                continue
            api_name = sd.query_hostapis(info["hostapi"])["name"]
        except sd.PortAudioError as error:
            errors.append(str(error))
            continue

        settings = dict(
            device=info["index"], samplerate=SAMPLE_RATE, channels=CHANNELS,
            dtype="int16", blocksize=0,
        )
        if api_name == "Windows WASAPI":
            # O mixer do Windows adapta taxa/canais ao formato do dispositivo.
            # Modo compartilhado permite coexistência com outros aplicativos.
            settings["extra_settings"] = sd.WasapiSettings(
                exclusive=False, auto_convert=True
            )
        for latency in ("low", "high"):
            try:
                stream = factory(latency=latency, **settings)
                return stream, f"{info['name']} ({api_name}, latência {latency})"
            except sd.PortAudioError as error:
                errors.append(f"{info['name']} / {api_name} / {latency}: {error}")
    details = "; ".join(errors)
    raise RuntimeError(
        f"Não foi possível abrir {label}. Confira --list-devices e selecione "
        f"--{'input' if kind == 'input' else 'output'}-device com o ID correto. "
        "No Windows, prefira a entrada Windows WASAPI; confira também as "
        "permissões de microfone e aplicativos usando o dispositivo. " + details
    )


class SoundDeviceAudio:
    def __init__(self, input_device=None, output_device=None):
        sd = load_sounddevice()
        self.input = None
        self.output = None
        try:
            self.input, self.input_description = open_audio_stream(sd, "input", input_device)
            self.output, self.output_description = open_audio_stream(sd, "output", output_device)
        except Exception:
            # Se apenas a saída falhar, libera o microfone antes de tentar de novo.
            self.close()
            raise

    def start(self):
        self.output.start()
        self.input.start()
        print(f"\n[Voz] Entrada: {self.input_description}")
        print(f"[Voz] Saída: {self.output_description}")

    def read(self):
        # blocksize=0 deixa o driver escolher seus buffers. Mesmo assim, nossa
        # leitura monta exatamente 320 amostras para cada datagrama de 20 ms.
        data, overflowed = self.input.read(FRAME_SAMPLES)
        return native_pcm(data)

    def write(self, data):
        self.output.write(native_pcm(data))

    def abort(self):
        # Desbloqueia read/write antes de esperar as threads terminarem.
        for stream in (self.input, self.output):
            if stream is not None:
                try:
                    stream.abort()
                except Exception:
                    pass

    def close(self):
        for stream in (self.input, self.output):
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass


class VoiceClient:
    def __init__(self, host, port, token, group, input_device=None,
                 output_device=None, audio_factory=SoundDeviceAudio):
        self.address = (host, port)
        self.token = bytes.fromhex(token)
        if len(self.token) != 16:
            raise ValueError("Token de voz inválido")
        self.group = group
        self.input_device = input_device
        self.output_device = output_device
        self.audio_factory = audio_factory
        self.audio = None
        self.socket = None
        self.stopped = threading.Event()
        self.muted = threading.Event()
        self.mixer = VoiceMixer()
        self.participants_revision = -1
        self.workers = []
        self.supervisor = None
        self.last_ack = 0
        self.last_error = None
        self.cleanup_lock = threading.Lock()
        self.cleaned = False

    def start(self):
        try:
            self.audio = self.audio_factory(self.input_device, self.output_device)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # UDP connect não cria conexão confiável: fixa destino e filtra origem.
            self.socket.connect(self.address)
            self.socket.settimeout(0.2)
            self._register()
            self.audio.start()
            for target in (self._receive_loop, self._capture_loop, self._playback_loop):
                worker = threading.Thread(target=target, daemon=True)
                self.workers.append(worker)
                worker.start()
            self.supervisor = threading.Thread(target=self._supervise, daemon=True)
            self.supervisor.start()
        except Exception:
            self.stopped.set()
            self._cleanup()
            raise

    def _register(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.socket.send(encode_packet(REGISTER, self.token))
            try:
                packet = decode_packet(self.socket.recv(MAX_DATAGRAM + 1))
                if packet.kind == REGISTERED and packet.token == self.token:
                    self.last_ack = time.monotonic()
                    return
            except (socket.timeout, ValueError):
                continue
        raise RuntimeError("Servidor UDP não respondeu. Confira endereço, porta e firewall")

    def set_participants(self, participants, revision=0):
        if revision < self.participants_revision:
            return False
        self.participants_revision = revision
        self.mixer.set_participants(p["speaker"] for p in participants)
        return True

    def set_muted(self, muted):
        self.muted.set() if muted else self.muted.clear()

    def _capture_loop(self):
        sequence = 0
        try:
            while not self.stopped.is_set():
                # A leitura bloqueante fornece o ritmo de 320 amostras a cada 20 ms.
                captured = self.audio.read()
                if self.stopped.is_set():
                    break
                # Mute mantém o relógio e envia silêncio, nunca os bytes do microfone.
                payload = SILENCE if self.muted.is_set() else captured
                self.socket.send(encode_packet(
                    AUDIO, self.token, sequence=sequence, payload=payload
                ))
                sequence = (sequence + 1) & SEQUENCE_MASK
        except Exception as error:
            self._fail(error)

    def _receive_loop(self):
        while not self.stopped.is_set():
            try:
                packet = decode_packet(self.socket.recv(MAX_DATAGRAM + 1))
                if packet.token != self.token:
                    continue
                if packet.kind == REGISTERED:
                    self.last_ack = time.monotonic()
                elif packet.kind == AUDIO:
                    self.mixer.add(packet.speaker, packet.sequence, packet.payload)
            except (socket.timeout, ValueError):
                continue
            except OSError as error:
                self._fail(error)
                break

    def _playback_loop(self):
        try:
            while not self.stopped.is_set():
                # Uma única saída toca a soma das vozes, não uma fila de falantes.
                self.audio.write(self.mixer.render())
        except Exception as error:
            self._fail(error)

    def _supervise(self):
        try:
            while not self.stopped.wait(1):
                self.socket.send(encode_packet(REGISTER, self.token))
                if time.monotonic() - self.last_ack > 5:
                    raise RuntimeError("Servidor de voz deixou de responder")
        except OSError as error:
            self._fail(error)
        except RuntimeError as error:
            self._fail(error)
        finally:
            self._cleanup()

    def _fail(self, error):
        if not self.stopped.is_set():
            self.last_error = str(error)
            print(f"\n[Voz] Áudio interrompido: {error}. Use /sairvoz e tente novamente.")
            self.stopped.set()

    def _cleanup(self):
        # Um único responsável fecha recursos, mesmo com falhas simultâneas.
        with self.cleanup_lock:
            if self.cleaned:
                return
            self.cleaned = True
            if self.socket is not None:
                self.socket.close()
            if self.audio is not None:
                self.audio.abort()
            for worker in self.workers:
                if worker is not threading.current_thread():
                    worker.join(timeout=1)
            if self.audio is not None:
                self.audio.close()

    def stop(self):
        self.stopped.set()
        if self.supervisor is not None:
            self.supervisor.join(timeout=4)
        else:
            self._cleanup()
