import React, { useState, useRef, useEffect } from 'react';
import { 
  Phone, Video, MoreVertical, Send, Mic, MicOff, Play, Pause, 
  Check, CheckCheck, Copy, RotateCcw, Sparkles, ShieldCheck, 
  AlertCircle, ArrowRight, Lock, Unlock, Volume2, Loader2, UserCheck
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { encodeWAV, resampleAudio } from '../utils/audio';

interface Message {
  id: string;
  sender: 'user' | 'bot' | 'anm_alert';
  text: string;
  timestamp: string;
  audioUrl?: string;
  isAudio?: boolean;
  audioDurationSec?: number;
  anmAlert?: {
    queue_id: number;
    beneficiary_name: string;
    rch_id: string;
    reported_by: string;
    priority: string;
    isApproved?: boolean;
  };
}

interface WorkerProfile {
  phone: string;
  name: string;
  role: 'ASHA' | 'ANM';
  village: string;
}

const WORKER_PROFILES: WorkerProfile[] = [
  { phone: '+919000012345', name: 'Geeta Devi', role: 'ASHA', village: 'Kishanpur' },
  { phone: '+919000098765', name: 'Nurse Kavita', role: 'ANM', village: 'Kishanpur Sub-Centre' },
];

interface WhatsAppChatSimulatorProps {
  onInteractionProcessed: () => void;
}

export const WhatsAppChatSimulator: React.FC<WhatsAppChatSimulatorProps> = ({
  onInteractionProcessed,
}) => {
  const [selectedWorker, setSelectedWorker] = useState<WorkerProfile>(WORKER_PROFILES[0]);
  const [language, setLanguage] = useState<'hi-IN' | 'mr-IN' | 'or-IN' | 'kn-IN'>('hi-IN');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [activeOtp, setActiveOtp] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [currentlyPlayingAudio, setCurrentlyPlayingAudio] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Audio recording refs
  const micContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const pcmChunksRef = useRef<Float32Array[]>([]);
  const timerRef = useRef<any>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, isRecording]);

  // Fetch worker session status on phone change
  const fetchSessionStatus = async (phone: string) => {
    try {
      const res = await fetch(`/api/whatsapp/session/${encodeURIComponent(phone)}`);
      if (res.ok) {
        const data = await res.json();
        setIsAuthenticated(Boolean(data.is_authenticated));
        setActiveOtp(data.active_otp || null);
      }
    } catch (e) {
      console.error('Error fetching session:', e);
    }
  };

  useEffect(() => {
    fetchSessionStatus(selectedWorker.phone);
    // Initial welcome message
    setMessages([
      {
        id: 'msg-welcome',
        sender: 'bot',
        text: `🇮🇳 *AAA-Setu (ANMOL-Sahayak)*\nOfficial Frontline Voice Bridge for MoHFW & MWCD.\n\nNamaste *${selectedWorker.name}* (${selectedWorker.role})!\nType *'Hi'* ya *'Login'* karke shuru karein.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  }, [selectedWorker]);

  // Audio Playback Handler
  const togglePlayAudio = (url: string) => {
    if (currentlyPlayingAudio === url) {
      audioPlayerRef.current?.pause();
      setCurrentlyPlayingAudio(null);
    } else {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      const player = new Audio(url);
      audioPlayerRef.current = player;
      player.play().catch(console.error);
      setCurrentlyPlayingAudio(url);
      player.onended = () => setCurrentlyPlayingAudio(null);
    }
  };

  // Reset Session (for quick testing)
  const handleResetSession = async () => {
    try {
      await fetch(`/api/whatsapp/reset-session/${encodeURIComponent(selectedWorker.phone)}`, { method: 'POST' });
      setIsAuthenticated(false);
      setActiveOtp(null);
      setMessages([
        {
          id: `reset-${Date.now()}`,
          sender: 'bot',
          text: `🔒 *Session Reset!* Aapka session reset ho gaya hai. Dobara login karne ke liye *'Hi'* bhejein.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (e) {
      console.error(e);
    }
  };

  // Send Text Message
  const handleSendText = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      text: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputText('');
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('sender_phone', selectedWorker.phone);
      formData.append('text', text.trim());
      formData.append('language_code', language);

      const res = await fetch('/api/whatsapp/simulate', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Failed to send WhatsApp message');
      const data = await res.json();

      // Update local state
      if (data.is_authenticated !== undefined) {
        setIsAuthenticated(data.is_authenticated);
      }
      if (data.otp) {
        setActiveOtp(data.otp);
      }

      // Add bot response message
      const botMsg: Message = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: data.text || 'Message processed.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      if (data.spoken_audio_b64) {
        botMsg.audioUrl = `data:audio/wav;base64,${data.spoken_audio_b64}`;
        botMsg.isAudio = true;
        // Auto play spoken audio
        togglePlayAudio(botMsg.audioUrl);
      }

      setMessages((prev) => [...prev, botMsg]);

      // If an ANM alert was generated, display it
      if (data.anm_alert) {
        const alertMsg: Message = {
          id: `anm-alert-${Date.now()}`,
          sender: 'anm_alert',
          text: data.anm_alert.message,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          anmAlert: {
            queue_id: data.anm_alert.queue_id,
            beneficiary_name: data.anm_alert.beneficiary_name,
            rch_id: data.anm_alert.rch_id,
            reported_by: data.anm_alert.reported_by,
            priority: data.anm_alert.priority,
            isApproved: false,
          },
        };
        setMessages((prev) => [...prev, alertMsg]);
      }

      onInteractionProcessed();
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'bot',
          text: `⚠️ *Error:* ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Start Voice Recording
  const startRecording = async () => {
    pcmChunksRef.current = [];
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioContextClass();
      micContextRef.current = ctx;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      micStreamRef.current = stream;

      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        pcmChunksRef.current.push(new Float32Array(inputData));
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          if (prev >= 60) {
            stopRecording();
            return 60;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err) {
      console.error('Mic access error:', err);
      alert('Microphone access required to record WhatsApp Voice Notes.');
    }
  };

  // Stop Recording & Send Audio to /api/whatsapp/simulate
  const stopRecording = async () => {
    if (!isRecording) return;
    setIsRecording(false);
    clearInterval(timerRef.current);

    if (processorRef.current) processorRef.current.disconnect();
    if (micStreamRef.current) micStreamRef.current.getTracks().forEach((t) => t.stop());
    if (micContextRef.current && micContextRef.current.state !== 'closed') {
      micContextRef.current.close().catch(() => {});
    }

    const recordedSeconds = recordingSeconds;
    const totalSamples = pcmChunksRef.current.reduce((acc, c) => acc + c.length, 0);
    if (totalSamples === 0) return;

    const merged = new Float32Array(totalSamples);
    let offset = 0;
    for (const chunk of pcmChunksRef.current) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    const inputSampleRate = micContextRef.current?.sampleRate || 44100;
    const resampled16k = resampleAudio(merged, inputSampleRate, 16000);
    const wavBlob = encodeWAV(resampled16k, 16000);
    const audioUrl = URL.createObjectURL(wavBlob);

    // Display sent audio bubble
    const userVoiceMsg: Message = {
      id: `usr-voice-${Date.now()}`,
      sender: 'user',
      text: '🎤 Voice Note',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      audioUrl: audioUrl,
      isAudio: true,
      audioDurationSec: recordedSeconds,
    };
    setMessages((prev) => [...prev, userVoiceMsg]);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('sender_phone', selectedWorker.phone);
      formData.append('audio_file', wavBlob, 'voice_note.wav');
      formData.append('language_code', language);

      const res = await fetch('/api/whatsapp/simulate', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('WhatsApp audio processing failed');
      const data = await res.json();

      if (data.is_authenticated !== undefined) {
        setIsAuthenticated(data.is_authenticated);
      }

      const botMsg: Message = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: data.text || 'Voice update recorded.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      if (data.spoken_audio_b64) {
        botMsg.audioUrl = `data:audio/wav;base64,${data.spoken_audio_b64}`;
        botMsg.isAudio = true;
        togglePlayAudio(botMsg.audioUrl);
      }

      setMessages((prev) => [...prev, botMsg]);

      // If an ANM alert was generated, show it
      if (data.anm_alert) {
        const alertMsg: Message = {
          id: `anm-alert-${Date.now()}`,
          sender: 'anm_alert',
          text: data.anm_alert.message,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          anmAlert: {
            queue_id: data.anm_alert.queue_id,
            beneficiary_name: data.anm_alert.beneficiary_name,
            rch_id: data.anm_alert.rch_id,
            reported_by: data.anm_alert.reported_by,
            priority: data.anm_alert.priority,
            isApproved: false,
          },
        };
        setMessages((prev) => [...prev, alertMsg]);
      }

      onInteractionProcessed();
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'bot',
          text: `⚠️ *Error:* ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle 1-Tap ANM Approval Click
  const handleApproveFromWhatsApp = async (queueId: number, messageId: string) => {
    try {
      const formData = new FormData();
      formData.append('sender_phone', '+919000098765'); // ANM Kavita
      formData.append('action', 'APPROVE');
      formData.append('queue_id', String(queueId));

      const res = await fetch('/api/whatsapp/simulate', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Approval failed');
      const data = await res.json();

      // Trigger celebratory confetti
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.6 },
      });

      // Update message status
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id === messageId && m.anmAlert) {
            return {
              ...m,
              anmAlert: { ...m.anmAlert, isApproved: true },
            };
          }
          return m;
        })
      );

      // Add confirmation reply
      setMessages((prev) => [
        ...prev,
        {
          id: `confirm-${Date.now()}`,
          sender: 'bot',
          text: data.text || `✅ Record #${queueId} approved & synced to RCH Portal and Poshan Tracker!`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);

      onInteractionProcessed();
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="bg-[#efeae2] rounded-2xl shadow-md border border-slate-300/80 overflow-hidden flex flex-col h-[calc(92vh-150px)] min-h-[550px] max-w-full font-sans">
      {/* 1. Worker Profile Switcher & Language Bar (Top Settings) */}
      <div className="bg-[#008069] text-white px-3 py-2 flex items-center justify-between text-xs border-b border-[#006e5a]">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-emerald-100">Simulate Frontline User:</span>
          <select
            value={selectedWorker.phone}
            onChange={(e) => {
              const w = WORKER_PROFILES.find((p) => p.phone === e.target.value);
              if (w) setSelectedWorker(w);
            }}
            className="bg-[#005e4d] text-white text-xs px-2 py-1 rounded border border-[#00705b] focus:outline-none"
          >
            {WORKER_PROFILES.map((p) => (
              <option key={p.phone} value={p.phone}>
                {p.name} ({p.role}) - {p.phone}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as any)}
            className="bg-[#005e4d] text-white text-[11px] px-2 py-1 rounded border border-[#00705b]"
          >
            <option value="hi-IN">Hindi (hi-IN)</option>
            <option value="mr-IN">Marathi (mr-IN)</option>
            <option value="or-IN">Odia (or-IN)</option>
            <option value="kn-IN">Kannada (kn-IN)</option>
          </select>

          <button
            onClick={handleResetSession}
            className="text-[10px] bg-red-800/80 hover:bg-red-700 text-white px-2 py-1 rounded flex items-center gap-1 transition-colors"
            title="Reset OTP authentication"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset Auth</span>
          </button>
        </div>
      </div>

      {/* 2. Official WhatsApp Business Header */}
      <div className="bg-[#075e54] text-white px-4 py-2.5 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-teal-500 to-emerald-400 flex items-center justify-center text-white font-bold text-sm shadow">
              🇮🇳
            </div>
            <span className="absolute bottom-0 right-0 w-3 h-3 bg-emerald-400 rounded-full border-2 border-[#075e54]" />
          </div>

          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="font-semibold text-sm leading-tight">AAA-Setu (ANMOL-Sahayak)</h2>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <p className="text-[11px] text-emerald-100 flex items-center gap-1">
              <span>Official Health Business Account •</span>
              <span className="font-semibold text-white">
                {isAuthenticated ? 'Authenticated 🟢' : 'OTP Verification Required 🔒'}
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-emerald-100">
          <Phone className="w-4 h-4 opacity-80 cursor-pointer" />
          <Video className="w-4 h-4 opacity-80 cursor-pointer" />
          <MoreVertical className="w-4 h-4 opacity-80 cursor-pointer" />
        </div>
      </div>

      {/* 3. OTP Fast-Fill Pill (If OTP is active and waiting) */}
      {!isAuthenticated && activeOtp && (
        <div className="bg-amber-100 text-amber-900 px-3 py-1.5 text-xs flex items-center justify-between border-b border-amber-200">
          <div className="flex items-center gap-1.5 font-medium">
            <Lock className="w-3.5 h-3.5 text-amber-700" />
            <span>Active OTP issued for {selectedWorker.name}: <strong>{activeOtp}</strong></span>
          </div>
          <button
            onClick={() => handleSendText(activeOtp)}
            className="bg-amber-600 hover:bg-amber-700 text-white text-[11px] font-semibold px-2.5 py-0.5 rounded shadow-xs flex items-center gap-1 transition-colors"
          >
            <span>Auto-fill OTP</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* 4. Chat Messages Scroll Area (WhatsApp Doodle Background) */}
      <div 
        className="flex-1 overflow-y-auto p-4 space-y-3.5"
        style={{
          backgroundImage: `radial-gradient(#d1d7db 0.75px, transparent 0.75px)`,
          backgroundSize: '16px 16px',
        }}
      >
        {/* Date Stamp */}
        <div className="flex justify-center my-1">
          <span className="bg-white/90 text-slate-500 text-[10px] uppercase font-bold px-3 py-0.5 rounded-full shadow-xs">
            Today
          </span>
        </div>

        {messages.map((m) => {
          const isUser = m.sender === 'user';
          const isAnmAlert = m.sender === 'anm_alert';

          // ANM Alert Card with 1-Tap Action Button
          if (isAnmAlert && m.anmAlert) {
            return (
              <div key={m.id} className="flex justify-start my-1 max-w-[90%]">
                <div className="bg-gradient-to-br from-teal-50 to-emerald-50 rounded-2xl rounded-tl-xs p-3.5 border border-emerald-200 shadow-md space-y-2 text-xs">
                  <div className="flex items-center gap-1.5 font-bold text-teal-900 border-b border-emerald-200/60 pb-1.5">
                    <UserCheck className="w-4 h-4 text-teal-700" />
                    <span>ANM Verification Request (Nurse Kavita)</span>
                  </div>

                  <pre className="text-slate-800 whitespace-pre-wrap font-sans text-xs leading-relaxed">
                    {m.text}
                  </pre>

                  {/* 1-Tap Interactive Action Button */}
                  {m.anmAlert.isApproved ? (
                    <div className="bg-emerald-600 text-white font-bold py-2 px-3 rounded-xl flex items-center justify-center gap-1.5 text-xs shadow-sm">
                      <Check className="w-4 h-4" />
                      <span>SYNCED TO RCH PORTAL & POSHAN</span>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleApproveFromWhatsApp(m.anmAlert!.queue_id, m.id)}
                      className="w-full bg-[#00a884] hover:bg-[#008f6f] text-white font-bold py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 text-xs shadow-sm transition-all hover:scale-102"
                    >
                      <span>✅ Approve & Sync to ANMOL</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}

                  <div className="text-[10px] text-slate-400 text-right">{m.timestamp}</div>
                </div>
              </div>
            );
          }

          return (
            <div
              key={m.id}
              className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl p-3 text-xs shadow-xs relative leading-relaxed ${
                  isUser
                    ? 'bg-[#d9fdd3] text-slate-900 rounded-tr-xs'
                    : 'bg-white text-slate-900 rounded-tl-xs border border-slate-200/60'
                }`}
              >
                {/* Voice Note Player (WhatsApp Audio Waveform Bubble) */}
                {m.isAudio && m.audioUrl ? (
                  <div className="flex items-center gap-3 py-1 min-w-[220px]">
                    <button
                      onClick={() => togglePlayAudio(m.audioUrl!)}
                      className={`w-9 h-9 rounded-full flex items-center justify-center text-white transition-colors shadow-xs ${
                        isUser ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-teal-700 hover:bg-teal-800'
                      }`}
                    >
                      {currentlyPlayingAudio === m.audioUrl ? (
                        <Pause className="w-4 h-4" />
                      ) : (
                        <Play className="w-4 h-4 ml-0.5" />
                      )}
                    </button>

                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-0.5 h-4">
                        {[40, 70, 30, 90, 60, 100, 40, 80, 50, 70, 90, 30, 60].map((h, i) => (
                          <span
                            key={i}
                            style={{ height: `${h}%` }}
                            className={`w-1 rounded-full ${
                              currentlyPlayingAudio === m.audioUrl
                                ? 'bg-emerald-600 animate-pulse'
                                : 'bg-slate-400'
                            }`}
                          />
                        ))}
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                        <span>Voice Note</span>
                        <span>{m.audioDurationSec ? `00:${String(m.audioDurationSec).padStart(2, '0')}` : 'Timbre TTS'}</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed">
                    {m.text}
                  </pre>
                )}

                {/* Copy button for formatted register entries */}
                {m.text.includes('MoHFW Register Entry') && (
                  <button
                    onClick={() => handleCopy(m.text, m.id)}
                    className="mt-2 w-full bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 text-[11px] font-semibold py-1 px-2 rounded-lg flex items-center justify-center gap-1 transition-colors"
                  >
                    {copiedId === m.id ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Copied for Paper Register!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-slate-500" />
                        <span>Copy for Physical Audit Register</span>
                      </>
                    )}
                  </button>
                )}

                {/* Timestamp & Read Receipts */}
                <div className="flex items-center justify-end gap-1 mt-1 text-[10px] text-slate-400">
                  <span>{m.timestamp}</span>
                  {isUser && <CheckCheck className="w-3.5 h-3.5 text-blue-500" />}
                </div>
              </div>
            </div>
          );
        })}

        {/* Loading Bubble */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white rounded-2xl rounded-tl-xs p-3 text-xs text-slate-500 flex items-center gap-2 shadow-xs border border-slate-200/60">
              <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
              <span>Transcribing with Prisma STT & Triaging...</span>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* 5. Live Audio Recording Bar OR Message Input Box */}
      {isRecording ? (
        <div className="bg-[#f0f2f5] p-3 border-t border-slate-200 flex items-center justify-between gap-3 animate-pulse">
          <div className="flex items-center gap-2 text-red-600 font-semibold text-xs">
            <span className="w-3 h-3 rounded-full bg-red-600 animate-ping" />
            <span>Recording Voice Note... ({String(recordingSeconds).padStart(2, '0')}s / 60s)</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setIsRecording(false);
                clearInterval(timerRef.current);
              }}
              className="text-xs text-slate-500 hover:text-slate-800 font-medium px-2 py-1"
            >
              Cancel
            </button>
            <button
              onClick={stopRecording}
              className="bg-red-600 hover:bg-red-700 text-white font-semibold text-xs px-4 py-2 rounded-full flex items-center gap-1.5 shadow-sm"
            >
              <MicOff className="w-3.5 h-3.5" />
              <span>Send Voice Note</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-[#f0f2f5] px-3 py-2 border-t border-slate-200 flex items-center gap-2">
          {/* Quick Action Pills if Unauthenticated */}
          {!isAuthenticated ? (
            <div className="flex-1 flex items-center gap-2">
              <button
                onClick={() => handleSendText('Hi')}
                className="bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold px-3 py-2 rounded-lg flex items-center gap-1.5 transition-colors"
              >
                <span>👋 Send "Hi" to Request OTP</span>
              </button>
              <input
                type="text"
                placeholder="Enter 4-digit OTP here..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                className="flex-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
              <button
                onClick={() => handleSendText()}
                className="p-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex-1 flex items-center gap-2">
              <input
                type="text"
                placeholder="Type details or tap Mic to record voice note..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                className="flex-1 bg-white border border-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />

              {inputText.trim() ? (
                <button
                  onClick={() => handleSendText()}
                  className="p-2.5 bg-[#00a884] text-white rounded-full hover:bg-[#008f6f] transition-colors shadow-xs"
                >
                  <Send className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={startRecording}
                  className="p-2.5 bg-[#00a884] hover:bg-[#008f6f] text-white rounded-full transition-all shadow-md hover:scale-105"
                  title="Hold or Tap to record WhatsApp Voice Note"
                >
                  <Mic className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

