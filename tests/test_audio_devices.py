"""Regressões da abertura de áudio: drivers simulados, sem capturar microfone."""

import unittest
from unittest.mock import Mock, patch

from client.voice_client import SoundDeviceAudio, open_audio_stream


class PortAudioError(Exception):
    pass


class AudioDeviceTests(unittest.TestCase):
    def setUp(self):
        self.sd = Mock()
        self.sd.PortAudioError = PortAudioError
        self.apis = [
            {"name": "MME", "default_input_device": 1, "default_output_device": 4},
            {"name": "Windows WASAPI", "default_input_device": 20, "default_output_device": 18},
        ]
        self.sd.query_hostapis.side_effect = lambda index=None: (
            self.apis if index is None else self.apis[index]
        )
        self.devices = {
            1: {"index": 1, "name": "Mic MME", "hostapi": 0,
                "max_input_channels": 2, "max_output_channels": 0},
            4: {"index": 4, "name": "Fones MME", "hostapi": 0,
                "max_input_channels": 0, "max_output_channels": 2},
            20: {"index": 20, "name": "Mic WASAPI", "hostapi": 1,
                 "max_input_channels": 2, "max_output_channels": 0},
            18: {"index": 18, "name": "Fones WASAPI", "hostapi": 1,
                 "max_input_channels": 0, "max_output_channels": 2},
        }
        self.sd.query_devices.side_effect = lambda device, kind: self.devices[
            device if device is not None else (1 if kind == "input" else 4)
        ]

    @patch("client.voice_client.sys.platform", "win32")
    def test_windows_prefers_shared_wasapi_and_preserves_network_rate(self):
        stream, description = open_audio_stream(self.sd, "input", None)
        self.assertIs(stream, self.sd.RawInputStream.return_value)
        options = self.sd.RawInputStream.call_args.kwargs
        self.assertEqual(options["device"], 20)
        self.assertEqual(options["samplerate"], 16000)
        self.assertEqual(options["blocksize"], 0)
        self.sd.WasapiSettings.assert_called_once_with(exclusive=False, auto_convert=True)
        self.assertIn("Windows WASAPI", description)

    @patch("client.voice_client.sys.platform", "win32")
    def test_explicit_device_is_respected_and_high_latency_is_fallback(self):
        self.sd.RawInputStream.side_effect = [PortAudioError("MME error 11"), Mock()]
        open_audio_stream(self.sd, "input", 1)
        attempts = self.sd.RawInputStream.call_args_list
        self.assertEqual([call.kwargs["device"] for call in attempts], [1, 1])
        self.assertEqual([call.kwargs["latency"] for call in attempts], ["low", "high"])
        self.sd.WasapiSettings.assert_not_called()

    @patch("client.voice_client.sys.platform", "win32")
    def test_default_device_used_if_wasapi_fails(self):
        self.sd.RawInputStream.side_effect = [PortAudioError("unavailable"),
                                              PortAudioError("unavailable"), Mock()]
        _, description = open_audio_stream(self.sd, "input", None)
        self.assertEqual(self.sd.RawInputStream.call_args.kwargs["device"], 1)
        self.assertIn("MME", description)

    @patch("client.voice_client.sys.platform", "linux")
    def test_other_platforms_use_default_device(self):
        open_audio_stream(self.sd, "input", None)
        self.assertEqual(self.sd.RawInputStream.call_args.kwargs["device"], 1)
        self.sd.WasapiSettings.assert_not_called()

    @patch("client.voice_client.sys.platform", "win32")
    def test_output_failure_closes_input_and_reports_correct_direction(self):
        microphone = self.sd.RawInputStream.return_value
        self.sd.RawOutputStream.side_effect = PortAudioError("output unavailable")
        with patch("client.voice_client.load_sounddevice", return_value=self.sd):
            with self.assertRaisesRegex(RuntimeError, "abrir saída de áudio"):
                SoundDeviceAudio()
        microphone.close.assert_called_once()

    @patch("client.voice_client.sys.platform", "win32")
    def test_wrong_direction_does_not_open_stream(self):
        with self.assertRaisesRegex(RuntimeError, "não possui canais"):
            open_audio_stream(self.sd, "input", 18)
        self.sd.RawInputStream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
