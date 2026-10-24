"""Garante que o diagnóstico de hardware não inicia captura nem faz login."""

import unittest
from unittest.mock import Mock, patch

from client.audio_diagnostics import check_audio


class AudioDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.sd = Mock(__version__="test")
        self.sd.get_portaudio_version.return_value = (1, "PortAudio teste")
        self.sd.query_devices.return_value = {
            "index": 1, "name": "Dispositivo teste", "hostapi": 0,
            "default_samplerate": 48000,
        }
        self.sd.query_hostapis.return_value = {"name": "API teste"}

    def test_probes_both_threads_without_starting_or_reading(self):
        streams = [Mock(input_description="mic", output_description="fone")
                   for _ in range(2)]
        with patch("client.audio_diagnostics.load_sounddevice", return_value=self.sd), \
                patch("client.audio_diagnostics.SoundDeviceAudio", side_effect=streams) as factory:
            report, success = check_audio(20, 18)
        self.assertTrue(success)
        self.assertIn("Thread principal: OK", report)
        self.assertIn("Thread secundária: OK", report)
        self.assertEqual(factory.call_count, 2)
        for stream in streams:
            stream.close.assert_called_once()
            stream.start.assert_not_called()
            stream.read.assert_not_called()
            stream.write.assert_not_called()

    def test_failure_in_worker_is_reported_as_failure(self):
        stream = Mock(input_description="mic", output_description="fone")
        with patch("client.audio_diagnostics.load_sounddevice", return_value=self.sd), \
                patch("client.audio_diagnostics.SoundDeviceAudio", side_effect=[
                    stream, RuntimeError("Invalid device -9996")
                ]):
            report, success = check_audio()
        self.assertFalse(success)
        self.assertIn("Thread principal: OK", report)
        self.assertIn("Thread secundária: FALHA: Invalid device -9996", report)
        stream.close.assert_called_once()

    def test_discovery_error_is_reported(self):
        with patch("client.audio_diagnostics.load_sounddevice", side_effect=RuntimeError("sem driver")), \
                patch("client.audio_diagnostics.SoundDeviceAudio") as factory:
            report, success = check_audio()
        self.assertFalse(success)
        self.assertIn("sem driver", report)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
