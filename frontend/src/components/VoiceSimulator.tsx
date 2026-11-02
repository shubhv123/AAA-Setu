import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Volume2, VolumeX, AlertTriangle, Play, Sparkles, Radio, Loader2 } from 'lucide-react';
import { encodeWAV, resampleAudio } from '../utils/audio';

interface VoiceSimulatorProps {
  onSessionProcessed: (result: any) => void;
  apiError: string | null;
  setApiError: (err: string | null) => void;
  isProcessing: boolean;
  setIsProcessing: (b: boolean) => void;
}

export const VoiceSimulator: React.FC<VoiceSimulatorProps> = ({
  onSessionProcessed,
  apiError,
  setApiError,
  isProcessing,
  setIsProcessing,
}) => {
  const [role, setRole] = useState<'ASHA_RELAY' | 'ANM_DIRECT'>('ASHA_RELAY');
  const [language, setLanguage] = useState<'hi-IN' | 'mr-IN' | 'or-IN' | 'kn-IN'>('hi-IN');
  const [noiseEnabled, setNoiseEnabled] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [transcriptPreview, setTranscriptPreview] = useState<string>('');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // Audio Context & Web Audio Noise Synthesizer (Simulating 75dB VHSND clinic noise: crowd chatter + baby cries + drone)
  const audioCtxRef = useRef<AudioContext | null>(null);
  const noiseNodeRef = useRef<AudioNode | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  
  // Web Audio 16kHz PCM WAV Recorder Refs
  const micContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const pcmChunksRef = useRef<Float32Array[]>([]);

  // 60-Second Demo Target Utterance (Sunita Devi, Joint Visit #8)
  const DEMO_PRESET_ASHA =
    "Main ASHA Geeta bol rahi hoon. RCH ID 999000104829, Sunita Devi, satva mahina, Joint Visit number 8. MCP card mein pichle camp ka BP 142 by 92 aur Hb 8.4 likha hai. Aaj Sunita ke pairon mein sujan hai aur tez sar dard hai. Uske paas 10 IFA goli bachi hain.";

  const DEMO_PRESET_ANM =
    "RCH ID 999000104830, Meena Kumari, ANC 2, weight 54 kilo, BP 118 by 76, Hb 11.2, urine albumin negative, TT booster given, 30 IFA tablets issued.";

  // Web Audio 75dB Clinic Noise Generator
  useEffect(() => {
    if (noiseEnabled) {
      try {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        const ctx = new AudioContextClass();
        audioCtxRef.current = ctx;

        // Create pink/brown noise for clinic ambient chatter & fan drone
        const bufferSize = ctx.sampleRate * 2;
        const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const output = noiseBuffer.getChannelData(0);
        let b0 = 0, b1 = 0, b2 = 0;
        for (let i = 0; i < bufferSize; i++) {
          const white = Math.random() * 2 - 1;
          b0 = 0.99886 * b0 + white * 0.0555179;
          b1 = 0.99332 * b1 + white * 0.0750759;
          b2 = 0.96900 * b2 + white * 0.1538520;
          output[i] = (b0 + b1 + b2) * 0.12;
        }

        const whiteNoise = ctx.createBufferSource();
        whiteNoise.buffer = noiseBuffer;
        whiteNoise.loop = true;

        const gainNode = ctx.createGain();
        gainNode.gain.setValueAtTime(0.18, ctx.currentTime);

        whiteNoise.connect(gainNode);
        gainNode.connect(ctx.destination);
        whiteNoise.start(0);
        noiseNodeRef.current = whiteNoise;
      } catch (e) {
        console.warn("Web Audio API not allowed without user gesture:", e);
      }
    } else {
      if (noiseNodeRef.current) {
        try {
          (noiseNodeRef.current as any).stop?.();
        } catch {}
        noiseNodeRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    }

    return () => {
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
      }
    };
  }, [noiseEnabled]);

  // Live Waveform Animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let offset = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const isLive = isRecording || noiseEnabled || isProcessing;
      ctx.lineWidth = 2;
      ctx.strokeStyle = isRecording ? '#dc2626' : noiseEnabled ? '#f59e0b' : '#3b82f6';
      ctx.beginPath();

      const sliceWidth = canvas.width / 40;
      let x = 0;

      for (let i = 0; i < 40; i++) {
        const amplitude = isLive ? Math.sin((i + offset) * 0.3) * (isRecording ? 18 : 10) + (Math.random() * 6 - 3) : 2;
        const y = canvas.height / 2 + amplitude;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }

      ctx.stroke();
      offset += 0.5;
      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [isRecording, noiseEnabled, isProcessing]);

  // Execute Pipeline via Preset Spoken Text
  const handleRunPreset = async (textToUse: string) => {
    setApiError(null);
    setIsProcessing(true);
    setTranscriptPreview(textToUse);

    try {
      const res = await fetch('/api/voice/process-json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          spoken_text: textToUse,
          source_role: role,
          language_code: language,
          offline_poshan: false,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      onSessionProcessed(data);

      if (data.spoken_audio_b64) {
        const audioSrc = `data:audio/wav;base64,${data.spoken_audio_b64}`;
        setAudioUrl(audioSrc);
        const player = new Audio(audioSrc);
        player.play().catch((e) => console.log('Audio autoplay prevented:', e));
      }
    } catch (err: any) {
      console.error('API Error in Voice Pipeline:', err);
      setApiError(err.message || String(err));
    } finally {
      setIsProcessing(false);
    }
  };

  // Live Microphone Recording (Genuine 16-bit 16kHz PCM WAV with RIFF Header)
  const startRecording = async () => {
    setApiError(null);
    pcmChunksRef.current = [];
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioContextClass();
      micContextRef.current = ctx;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
      });
      micStreamRef.current = stream;

      const source = ctx.createMediaStreamSource(stream);
      // Buffer size 4096, 1 input channel, 1 output channel
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const channelData = e.inputBuffer.getChannelData(0);
        pcmChunksRef.current.push(new Float32Array(channelData));
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      setIsRecording(true);
    } catch (e: any) {
      setApiError(`Microphone access error: ${e.message}`);
    }
  };

  const stopRecording = async () => {
    if (!isRecording) return;
    setIsRecording(false);

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }

    const ctx = micContextRef.current;
    const sourceSampleRate = ctx ? ctx.sampleRate : 48000;
    if (ctx) {
      ctx.close().catch(() => {});
      micContextRef.current = null;
    }

    const chunks = pcmChunksRef.current;
    if (chunks.length === 0) return;

    const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const c of chunks) {
      merged.set(c, offset);
      offset += c.length;
    }

    // Resample from browser hardware rate (e.g. 48000/44100) to 16000 Hz
    const resampled = resampleAudio(merged, sourceSampleRate, 16000);
    // Encode to genuine 16-bit linear PCM WAV with standard RIFF header
    const wavBlob = encodeWAV(resampled, 16000);

    await uploadAudio(wavBlob);
  };

  const uploadAudio = async (blob: Blob) => {
    setIsProcessing(true);
    try {
      const formData = new FormData();
      formData.append('audio_file', blob, 'recording.wav');
      formData.append('source_role', role);
      formData.append('language_code', language);

      const res = await fetch('/api/voice/process', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setTranscriptPreview(data.transcript || 'Transcribed audio successfully');
      onSessionProcessed(data);

      if (data.spoken_audio_b64) {
        const audioSrc = `data:audio/wav;base64,${data.spoken_audio_b64}`;
        setAudioUrl(audioSrc);
        const player = new Audio(audioSrc);
        player.play().catch(() => {});
      }
    } catch (err: any) {
      setApiError(err.message || String(err));
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-blue-50 text-blue-700 rounded-lg">
            <Radio className="w-5 h-5 animate-pulse text-blue-600" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-800">Voice Simulator & Audio Console</h2>
            <p className="text-xs text-slate-500">Gnani Prisma STT (16kHz) + Evon v3.3 + Timbre v2.5</p>
          </div>
        </div>

        {/* 75dB Noise Canceller Toggle */}
        <div className="flex items-center gap-2 bg-amber-50 px-3 py-1.5 rounded-full border border-amber-200">
          {noiseEnabled ? <Volume2 className="w-4 h-4 text-amber-700" /> : <VolumeX className="w-4 h-4 text-slate-400" />}
          <span className="text-xs font-medium text-amber-900">75dB VHSND Noise</span>
          <button
            onClick={() => setNoiseEnabled(!noiseEnabled)}
            className={`w-9 h-5 flex items-center rounded-full p-1 transition-colors ${
              noiseEnabled ? 'bg-amber-600' : 'bg-slate-300'
            }`}
            title="Inject simulated 75dB clinic noise (baby crying, crowd chatter, ceiling fan)"
          >
            <div
              className={`bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition-transform ${
                noiseEnabled ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Mode & Language Selectors */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Frontline Worker Role</label>
          <div className="grid grid-cols-2 gap-1.5 bg-slate-100 p-1 rounded-lg text-xs">
            <button
              onClick={() => setRole('ASHA_RELAY')}
              className={`py-1.5 px-2 rounded-md font-medium transition-all ${
                role === 'ASHA_RELAY' ? 'bg-white shadow-sm text-blue-700 font-semibold' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              ASHA Home Visit
            </button>
            <button
              onClick={() => setRole('ANM_DIRECT')}
              className={`py-1.5 px-2 rounded-md font-medium transition-all ${
                role === 'ANM_DIRECT' ? 'bg-white shadow-sm text-teal-700 font-semibold' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              ANM Camp Mode
            </button>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Language (Gnani Prisma)</label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as any)}
            className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="hi-IN">Hindi (हिंदी)</option>
            <option value="mr-IN">Marathi (मराठी)</option>
            <option value="or-IN">Odia (ଓଡ଼ିଆ)</option>
            <option value="kn-IN">Kannada (ಕನ್ನಡ)</option>
          </select>
        </div>
      </div>

      {/* Waveform Canvas */}
      <div className="bg-slate-900 rounded-lg p-3 text-center relative overflow-hidden">
        <canvas ref={canvasRef} width={400} height={40} className="w-full h-10" />
        <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1 font-mono">
          <span>SAMPLING: 16 kHz PCM</span>
          <span>{noiseEnabled ? '75dB NOISE MIXED' : 'CLEAN AUDIO'}</span>
          <span>ITN: TRANSCRIBE</span>
        </div>
      </div>

      {/* Preset Demo Utterance Button (The 60-Second Video Target) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            Instant Demo Utterance:
          </span>
          <span className="text-[10px] bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full font-medium">
            Sunita Devi (Visit #8)
          </span>
        </div>

        <button
          onClick={() => handleRunPreset(role === 'ASHA_RELAY' ? DEMO_PRESET_ASHA : DEMO_PRESET_ANM)}
          disabled={isProcessing || isRecording}
          className="w-full text-left bg-blue-50/60 hover:bg-blue-50 border border-blue-200 rounded-lg p-2.5 transition-all text-xs text-slate-700 group disabled:opacity-50"
        >
          <div className="flex items-start gap-2">
            <Play className="w-4 h-4 text-blue-600 mt-0.5 shrink-0 group-hover:scale-110 transition-transform" />
            <p className="italic leading-relaxed">
              "{role === 'ASHA_RELAY' ? DEMO_PRESET_ASHA : DEMO_PRESET_ANM}"
            </p>
          </div>
        </button>
      </div>

      {/* Live Mic Action Buttons */}
      <div className="flex items-center gap-2 pt-1">
        {!isRecording ? (
          <button
            onClick={startRecording}
            disabled={isProcessing}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 text-xs shadow-sm transition-colors disabled:opacity-50"
          >
            <Mic className="w-4 h-4" />
            Speak Live with Mic
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="flex-1 bg-slate-900 hover:bg-black text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 text-xs shadow-sm transition-colors animate-pulse"
          >
            <MicOff className="w-4 h-4 text-red-400" />
            Stop & Process Audio
          </button>
        )}

        {isProcessing && (
          <div className="flex items-center gap-2 text-xs text-blue-600 font-medium px-3 py-2 bg-blue-50 rounded-lg border border-blue-200 animate-pulse">
            <Loader2 className="w-4 h-4 animate-spin" />
            Processing...
          </div>
        )}
      </div>

      {/* Spoken Alert Audio Player */}
      {audioUrl && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-emerald-600 animate-bounce" />
            <span className="text-xs font-semibold text-emerald-900">Timbre v2.5 Spoken Triage Alert</span>
          </div>
          <audio controls src={audioUrl} className="h-7 w-48" />
        </div>
      )}

      {/* Direct API Error Alert */}
      {apiError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold">Gnani API Exception Surfaced:</p>
            <p className="font-mono text-[11px] break-all">{apiError}</p>
          </div>
        </div>
      )}

      {/* Live Transcript Display */}
      {transcriptPreview && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs text-slate-700">
          <span className="font-semibold text-slate-900 block mb-0.5">Transcript (Prisma ITN):</span>
          <p className="text-slate-600">{transcriptPreview}</p>
        </div>
      )}
    </div>
  );
};

