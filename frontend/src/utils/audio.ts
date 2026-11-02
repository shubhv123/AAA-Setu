/**
 * Encodes Float32 audio samples into a genuine 16-bit linear PCM WAV Blob
 * with standard RIFF header at the target sample rate (default 16000 Hz).
 * Guaranteed to produce a valid RIFF/WAVE container for Gnani Prisma STT.
 */

export function encodeWAV(samples: Float32Array, sampleRate: number = 16000): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  // 1. "RIFF" chunk descriptor
  writeString(view, 0, 'RIFF');
  // 36 + SubChunk2Size = 36 + samples.length * 2
  view.setUint32(4, 36 + samples.length * 2, true);
  // "WAVE"
  writeString(view, 8, 'WAVE');

  // 2. "fmt " sub-chunk
  writeString(view, 12, 'fmt ');
  // Subchunk1Size (16 for PCM)
  view.setUint32(16, 16, true);
  // AudioFormat (1 = Linear PCM)
  view.setUint16(20, 1, true);
  // NumChannels (1 = Mono)
  view.setUint16(22, 1, true);
  // SampleRate (16000)
  view.setUint32(24, sampleRate, true);
  // ByteRate = SampleRate * NumChannels * BitsPerSample/8 = sampleRate * 2
  view.setUint32(28, sampleRate * 2, true);
  // BlockAlign = NumChannels * BitsPerSample/8 = 2
  view.setUint16(32, 2, true);
  // BitsPerSample = 16
  view.setUint16(34, 16, true);

  // 3. "data" sub-chunk
  writeString(view, 36, 'data');
  // Subchunk2Size = NumSamples * NumChannels * BitsPerSample/8
  view.setUint32(40, samples.length * 2, true);

  // 4. Write 16-bit linear PCM samples
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    // Clamp float between -1.0 and 1.0
    const s = Math.max(-1, Math.min(1, samples[i]));
    // Convert to signed 16-bit int (-32768 to 32767)
    const val = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(offset, val, true);
    offset += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}

/**
 * Resamples a Float32Array from sourceSampleRate down to targetSampleRate (e.g. 48000 -> 16000).
 */
export function resampleAudio(
  samples: Float32Array,
  sourceSampleRate: number,
  targetSampleRate: number = 16000
): Float32Array {
  if (sourceSampleRate === targetSampleRate) {
    return samples;
  }
  const ratio = sourceSampleRate / targetSampleRate;
  const newLength = Math.round(samples.length / ratio);
  const result = new Float32Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const originalIndex = i * ratio;
    const indexFloor = Math.floor(originalIndex);
    const indexCeil = Math.min(samples.length - 1, indexFloor + 1);
    const fraction = originalIndex - indexFloor;
    // Linear interpolation
    result[i] = (1 - fraction) * samples[indexFloor] + fraction * samples[indexCeil];
  }

  return result;
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

