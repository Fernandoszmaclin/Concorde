"""Diagnóstico de abertura no ambiente real do usuário, sem gravar áudio."""

import sys
import threading

from client.voice_client import SoundDeviceAudio, load_sounddevice


def check_audio(input_device=None, output_device=None):
    lines = [
        "Diagnóstico de áudio: streams serão abertos e fechados, sem captura.",
        f"Python: {sys.executable}",
        f"Versão Python: {sys.version.split()[0]}",
    ]
    try:
        sd = load_sounddevice()
        lines.append(f"sounddevice: {sd.__version__}")
        lines.append(f"PortAudio: {sd.get_portaudio_version()[1]}")
        for kind, selected in (("input", input_device), ("output", output_device)):
            device = sd.query_devices(selected, kind)
            api = sd.query_hostapis(device["hostapi"])["name"]
            lines.append(
                f"Dispositivo {kind}: {device['index']} / {device['name']} / {api} / "
                f"taxa padrão {device['default_samplerate']:.0f} Hz"
            )
    except Exception as error:
        lines.append(f"FALHA na identificação de dispositivos: {error}")
        return "\n".join(lines), False

    results = []

    def probe(label):
        audio = None
        try:
            audio = SoundDeviceAudio(input_device, output_device)
            lines.append(f"{label}: OK")
            lines.append(f"  Entrada: {audio.input_description}")
            lines.append(f"  Saída: {audio.output_description}")
            results.append(True)
        except Exception as error:
            lines.append(f"{label}: FALHA: {error}")
            results.append(False)
        finally:
            if audio is not None:
                # Não chamamos start(), read() ou write(): nenhum som é capturado.
                audio.close()

    probe("Thread principal")
    # A chamada normal é iniciada a partir do receptor TCP. Comparamos as duas
    # situações no MESMO processo/terminal, em vez de atribuir a falha ao driver.
    worker = threading.Thread(target=probe, args=("Thread secundária",), daemon=True)
    worker.start()
    worker.join()
    lines.append("Diagnóstico concluído; nenhum stream foi iniciado.")
    return "\n".join(lines), all(results)
