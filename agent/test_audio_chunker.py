import unittest
import io
import wave
from agent.main import split_wav_bytes

class TestAudioChunker(unittest.TestCase):
    def _create_wav(self, duration_sec: float, sample_rate: int = 16000) -> bytes:
        num_samples = int(duration_sec * sample_rate)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b'\x00\x00' * num_samples)
        return buf.getvalue()

    def test_short_audio_not_chunked(self):
        """Audio under 24 seconds is returned as a single chunk."""
        wav_bytes = self._create_wav(15.0)
        chunks = split_wav_bytes(wav_bytes, max_chunk_sec=24.0)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], wav_bytes)

    def test_60_second_audio_chunked(self):
        """60-second audio is safely split into chunks <= 24s each."""
        wav_bytes = self._create_wav(60.0)
        chunks = split_wav_bytes(wav_bytes, max_chunk_sec=24.0)
        self.assertEqual(len(chunks), 3)

        total_frames = 0
        for idx, chunk in enumerate(chunks):
            self.assertTrue(chunk.startswith(b'RIFF'))
            with wave.open(io.BytesIO(chunk), 'rb') as cr:
                sec = cr.getnframes() / cr.getframerate()
                self.assertLessEqual(sec, 24.1)
                total_frames += cr.getnframes()

        self.assertEqual(total_frames, 60 * 16000)

if __name__ == "__main__":
    unittest.main()

