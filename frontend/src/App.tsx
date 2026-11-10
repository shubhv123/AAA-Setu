import React, { useState, useEffect, useRef } from 'react';
import confetti from 'canvas-confetti';
import { 
  Activity, Tablet, HeartPulse, FileSpreadsheet, MessageSquare, 
  Radio, RefreshCw, AlertOctagon, Sparkles, Mic, MicOff, Send, 
  CheckCircle2, ArrowRight, UserCheck, ShieldCheck, ChevronRight,
  Settings, Share2
} from 'lucide-react';
import { encodeWAV, resampleAudio } from './utils/audio';
import { UnifiedChatView, ChatMessage } from './components/UnifiedChatView';
import { AnmolQueuePanel } from './components/AnmolQueuePanel';
import { PoshanSyncPanel } from './components/PoshanSyncPanel';
import { PaperRegister } from './components/PaperRegister';
import { VoiceSimulator } from './components/VoiceSimulator';

type TabType = 'chat' | 'anmol' | 'poshan' | 'register' | 'audio';

interface WorkerOption {
  phone: string;
  name: string;
  role: 'ASHA' | 'ANM';
  village: string;
}

const WORKERS: WorkerOption[] = [
  { phone: '+919000012345', name: 'Geeta Devi', role: 'ASHA', village: 'Kishanpur' },
  { phone: '+919000098765', name: 'Nurse Kavita', role: 'ANM', village: 'Kishanpur Sub-Centre' },
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  const [selectedWorker, setSelectedWorker] = useState<WorkerOption>(WORKERS[0]);
  const [queue, setQueue] = useState<any[]>([]);
  const [poshanVisits, setPoshanVisits] = useState<any[]>([]);
  const [registerRecords, setRegisterRecords] = useState<any[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [isApproving, setIsApproving] = useState<number | null>(null);
  const [criticalAlert, setCriticalAlert] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [activeOtp, setActiveOtp] = useState<string | null>(null);
  const [currentlyPlayingAudio, setCurrentlyPlayingAudio] = useState<string | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Floating Input Bar State
  const [floatingInput, setFloatingInput] = useState('');
  const [isFloatingSending, setIsFloatingSending] = useState(false);
  const [isFloatingRecording, setIsFloatingRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  // Audio Console Props
  const [isProcessing, setIsProcessing] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Floating Audio Recording Refs
  const micContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const pcmChunksRef = useRef<Float32Array[]>([]);
  const timerRef = useRef<any>(null);

  // Fetch initial state from backend
  const fetchAllData = async () => {
    try {
      const [queueRes, poshanRes, registerRes] = await Promise.all([
        fetch('/api/anmol/queue'),
        fetch('/api/poshan/visits'),
        fetch('/api/paper-register'),
      ]);

      if (queueRes.ok) setQueue(await queueRes.json());
      if (poshanRes.ok) setPoshanVisits(await poshanRes.json());
      if (registerRes.ok) setRegisterRecords(await registerRes.json());
    } catch (e) {
      console.error('Failed to fetch initial state:', e);
    }
  };

  // Fetch Worker Auth Session Status
  const fetchSessionStatus = async (phone: string) => {
    try {
      const res = await fetch(`/api/whatsapp/session/${encodeURIComponent(phone)}`);
      if (res.ok) {
        const data = await res.json();
        setIsAuthenticated(Boolean(data.is_authenticated));
        setActiveOtp(data.active_otp || null);
      }
    } catch (e) {
      console.error('Failed to fetch session:', e);
    }
  };

  useEffect(() => {
    fetchAllData();
    fetchSessionStatus(selectedWorker.phone);

    // Setup Real-time WebSocket Listener
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let socket: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWs = () => {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setWsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { event: eventType, data } = payload;

          if (eventType === 'voice_processed') {
            const prio = data?.recommendation?.priority_level || data?.triage?.severity;
            if (prio === 'URGENT_PHC_REFERRAL' || prio === 'CRITICAL_RED_SEAL') {
              setCriticalAlert(
                `🚨 URGENT PHC REFERRAL: Elevated risk indicators observed for ${data.extracted?.beneficiary_name || 'Beneficiary'}! Immediate Medical Officer evaluation advised.`
              );
            }
            fetchAllData();
          } else if (eventType === 'anmol_queue_updated') {
            fetchAllData();
          } else if (eventType === 'poshan_synced') {
            fetchAllData();
          } else if (eventType === 'register_row_added') {
            fetchAllData();
          } else if (eventType === 'database_reset') {
            setCriticalAlert(null);
            setMessages([]);
            fetchAllData();
            fetchSessionStatus(selectedWorker.phone);
          }
        } catch (err) {
          console.error('Error handling WS message:', err);
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
        reconnectTimeout = setTimeout(connectWs, 2000);
      };

      socket.onerror = (err) => {
        socket?.close();
      };
    };

    connectWs();

    return () => {
      clearTimeout(reconnectTimeout);
      socket?.close();
    };
  }, [selectedWorker.phone]);

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

  // Dispatch Text Handler (Single Unified Entry Point)
  const handleSendText = async (customText?: string) => {
    const textToSend = (customText !== undefined ? customText : floatingInput).trim();
    if (!textToSend || isFloatingSending) return;

    setFloatingInput('');
    setIsFloatingSending(true);

    const userMsgId = `user-${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);

    try {
      const formData = new FormData();
      formData.append('sender_phone', selectedWorker.phone);
      formData.append('text', textToSend);
      formData.append('language_code', 'hi-IN');

      const res = await fetch('/api/whatsapp/simulate', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to dispatch text');
      }

      const reply = await res.json();
      await fetchSessionStatus(selectedWorker.phone);

      let audioUrl: string | undefined = undefined;
      if (reply.spoken_audio_b64) {
        audioUrl = `data:audio/wav;base64,${reply.spoken_audio_b64}`;
        togglePlayAudio(audioUrl);
      }

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: reply.text || 'Record processed successfully.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        audioUrl,
        extracted: reply.extracted,
        recommendation: reply.recommendation,
        anmAlert: reply.anm_alert,
        otpPrompt: reply.type === 'otp_prompt' ? { otp: reply.otp, phone: reply.phone } : undefined,
      };

      setMessages((prev) => [...prev, botMsg]);
      await fetchAllData();
    } catch (e: any) {
      alert(`Dispatch error: ${e.message}`);
    } finally {
      setIsFloatingSending(false);
    }
  };

  // Dispatch Audio Recording Handler
  const startFloatingVoice = async () => {
    if (isFloatingRecording) {
      stopFloatingVoice();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioContextClass();
      micContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      pcmChunksRef.current = [];

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        pcmChunksRef.current.push(new Float32Array(inputData));
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      setIsFloatingRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);
    } catch (err: any) {
      alert(`Microphone permission error: ${err.message}`);
    }
  };

  const stopFloatingVoice = async () => {
    if (!isFloatingRecording) return;

    clearInterval(timerRef.current);
    const recordedSecs = recordingSeconds;
    setIsFloatingRecording(false);

    if (processorRef.current && micContextRef.current) {
      processorRef.current.disconnect();
      micContextRef.current.close();
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
    }

    const totalSamples = pcmChunksRef.current.reduce((acc, c) => acc + c.length, 0);
    if (totalSamples === 0) return;

    const merged = new Float32Array(totalSamples);
    let offset = 0;
    for (const chunk of pcmChunksRef.current) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    const currentSampleRate = micContextRef.current?.sampleRate || 44100;
    const resampled = resampleAudio(merged, currentSampleRate, 16000);
    const wavBlob = encodeWAV(resampled, 16000);
    const blobUrl = URL.createObjectURL(wavBlob);

    const userVoiceMsg: ChatMessage = {
      id: `user-voice-${Date.now()}`,
      sender: 'user',
      text: '🎤 Voice Note recorded',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      audioUrl: blobUrl,
      audioDurationSec: recordedSecs || 2,
    };
    setMessages((prev) => [...prev, userVoiceMsg]);

    setIsFloatingSending(true);
    try {
      const formData = new FormData();
      formData.append('sender_phone', selectedWorker.phone);
      formData.append('audio_file', wavBlob, 'voice_note.wav');
      formData.append('language_code', 'hi-IN');

      const res = await fetch('/api/whatsapp/simulate', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Voice processing failed');
      }

      const reply = await res.json();
      await fetchSessionStatus(selectedWorker.phone);

      let replyAudioUrl: string | undefined = undefined;
      if (reply.spoken_audio_b64) {
        replyAudioUrl = `data:audio/wav;base64,${reply.spoken_audio_b64}`;
        togglePlayAudio(replyAudioUrl);
      }

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: reply.text || 'Voice update transcribed and triaged.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        audioUrl: replyAudioUrl,
        extracted: reply.extracted,
        recommendation: reply.recommendation,
        anmAlert: reply.anm_alert,
      };

      setMessages((prev) => [...prev, botMsg]);
      await fetchAllData();
    } catch (err: any) {
      alert(`Voice error: ${err.message}`);
    } finally {
      setIsFloatingSending(false);
    }
  };

  // One-Tap Approval by ANM
  const handleApprove = async (queueId: number) => {
    setIsApproving(queueId);
    try {
      const res = await fetch(`/api/anmol/approve/${queueId}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to approve');

      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.6 },
      });

      await fetchAllData();
    } catch (e: any) {
      alert(`Approval error: ${e.message}`);
    } finally {
      setIsApproving(null);
    }
  };

  // Sync Offline Poshan Visit
  const handleSyncPoshan = async (visitId: number) => {
    try {
      const res = await fetch(`/api/poshan/sync/${visitId}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to sync Poshan visit');
      await fetchAllData();
    } catch (e: any) {
      alert(`Poshan sync error: ${e.message}`);
    }
  };

  // Reset Demo to Baseline
  const handleReset = async () => {
    if (!window.confirm('Clear all patient records and reset authentication sessions?')) return;
    setIsResetting(true);
    try {
      const res = await fetch('/api/reset', { method: 'POST' });
      if (res.ok) {
        setCriticalAlert(null);
        setFloatingInput('');
        setMessages([]);
        await fetchAllData();
        await fetchSessionStatus(selectedWorker.phone);
      }
    } finally {
      setIsResetting(false);
    }
  };

  const pendingApprovalsCount = queue.filter(
    (q) => q.anm_approval_status === 'PENDING_VERIFICATION'
  ).length;

  return (
    <div className="min-h-screen bg-[#eceef1] flex items-center justify-center p-3 md:p-6 font-sans antialiased text-slate-800">
      {/* Framed Application Window (Faithful reproduction of frame_004.png) */}
      <div className="w-full max-w-[1600px] h-[92vh] max-h-[960px] bg-white rounded-[32px] shadow-2xl border border-slate-200/80 flex overflow-hidden relative">
        
        {/* ========================================================= */}
        {/* 1. SLIM ICON RAIL (64px wide, matching frame_004.png)      */}
        {/* ========================================================= */}
        <aside className="w-16 bg-[#f7f8fa] border-r border-slate-200/60 flex flex-col items-center py-5 justify-between shrink-0 select-none z-10">
          <div className="flex flex-col items-center gap-5">
            {/* Blue Gradient Sphere Logo */}
            <button
              onClick={() => setActiveTab('chat')}
              className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 via-indigo-500 to-sky-400 p-0.5 shadow-md flex items-center justify-center hover:scale-105 transition-transform"
              title="AAA-Setu Sovereign Voice AI"
            >
              <div className="w-full h-full bg-slate-900 rounded-full flex items-center justify-center">
                <Activity className="w-4 h-4 text-sky-400" />
              </div>
            </button>

            {/* Navigation Outline Icons */}
            <div className="flex flex-col items-center gap-3">
              <button
                onClick={() => setActiveTab('chat')}
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                  activeTab === 'chat'
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-slate-400 hover:text-slate-800 hover:bg-slate-200/50'
                }`}
                title="Chat"
              >
                <MessageSquare className="w-4 h-4" />
              </button>

              <button
                onClick={() => setActiveTab('anmol')}
                className={`w-10 h-10 rounded-xl flex items-center justify-center relative transition-all ${
                  activeTab === 'anmol'
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-slate-400 hover:text-slate-800 hover:bg-slate-200/50'
                }`}
                title="ANMOL Queue"
              >
                <Tablet className="w-4 h-4" />
                {pendingApprovalsCount > 0 && (
                  <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-amber-500 rounded-full ring-2 ring-white" />
                )}
              </button>

              <button
                onClick={() => setActiveTab('poshan')}
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                  activeTab === 'poshan'
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-slate-400 hover:text-slate-800 hover:bg-slate-200/50'
                }`}
                title="Poshan Tracker"
              >
                <HeartPulse className="w-4 h-4" />
              </button>

              <button
                onClick={() => setActiveTab('register')}
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                  activeTab === 'register'
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-slate-400 hover:text-slate-800 hover:bg-slate-200/50'
                }`}
                title="Paper Register"
              >
                <FileSpreadsheet className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Bottom Icons: Reset DB & Profile Avatar */}
          <div className="flex flex-col items-center gap-3">
            <button
              onClick={handleReset}
              disabled={isResetting}
              className="w-9 h-9 rounded-xl flex items-center justify-center text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
              title="Clear Database to 0 Records"
            >
              <RefreshCw className={`w-4 h-4 ${isResetting ? 'animate-spin text-red-500' : ''}`} />
            </button>

            {/* Profile Avatar circle with initial S / G matching frame_004.png */}
            <button
              onClick={() => {
                const next = selectedWorker.role === 'ASHA' ? WORKERS[1] : WORKERS[0];
                setSelectedWorker(next);
              }}
              className="relative"
              title={`Logged in: ${selectedWorker.name} (${selectedWorker.role}). Click to switch.`}
            >
              <div className="w-9 h-9 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-semibold shadow-xs">
                {selectedWorker.name.charAt(0)}
              </div>
              <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-500 rounded-full ring-2 ring-white" />
            </button>
          </div>
        </aside>

        {/* ========================================================= */}
        {/* 2. SUB-SIDEBAR (260px wide, Clean Tabs ONLY, No Demos)     */}
        {/* ========================================================= */}
        <aside className="w-64 bg-[#fafbfc] border-r border-slate-200/60 flex flex-col p-4 justify-between shrink-0 select-none">
          <div className="space-y-4">
            {/* Header Title with Search Icon matching frame_004.png */}
            <div className="flex items-center justify-between px-1">
              <span className="text-sm font-bold text-slate-900 tracking-tight">Chat</span>
              <Sparkles className="w-4 h-4 text-slate-400" />
            </div>

            {/* + New Chat Black Pill Button matching frame_004.png */}
            <button
              onClick={() => {
                setActiveTab('chat');
                setMessages([]);
                setFloatingInput('');
              }}
              className="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 shadow-xs transition-all"
            >
              <span>+ New Chat</span>
              <Sparkles className="w-3.5 h-3.5 text-sky-300" />
            </button>

            {/* Clean Tab Options ONLY: Chat, ANMOL, Poshan, Register */}
            <div className="space-y-1 pt-2">
              <button
                onClick={() => setActiveTab('chat')}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  activeTab === 'chat'
                    ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-semibold'
                    : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <MessageSquare className="w-4 h-4 text-blue-600" />
                  <span>Chat</span>
                </div>
              </button>

              <button
                onClick={() => setActiveTab('anmol')}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  activeTab === 'anmol'
                    ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-semibold'
                    : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Tablet className="w-4 h-4 text-teal-600" />
                  <span>ANMOL</span>
                </div>
                {pendingApprovalsCount > 0 && (
                  <span className="text-[10px] bg-amber-500 text-white font-bold px-1.5 py-0.2 rounded-full">
                    {pendingApprovalsCount}
                  </span>
                )}
              </button>

              <button
                onClick={() => setActiveTab('poshan')}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  activeTab === 'poshan'
                    ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-semibold'
                    : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <HeartPulse className="w-4 h-4 text-purple-600" />
                  <span>Poshan Tracker</span>
                </div>
              </button>

              <button
                onClick={() => setActiveTab('register')}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  activeTab === 'register'
                    ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-semibold'
                    : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <FileSpreadsheet className="w-4 h-4 text-emerald-700" />
                  <span>Paper Register</span>
                </div>
              </button>
            </div>
          </div>

          {/* Bottom Left Drawer: Worker Switcher & Clear DB */}
          <div className="pt-3 border-t border-slate-200/60 space-y-2">
            <div className="bg-white border border-slate-200/70 p-2.5 rounded-xl flex items-center justify-between text-xs shadow-2xs">
              <div>
                <p className="text-[10px] text-slate-400">Frontline User</p>
                <p className="font-semibold text-slate-800 text-[11px] truncate max-w-[120px]">
                  {selectedWorker.name}
                </p>
              </div>
              <button
                onClick={() => {
                  const next = selectedWorker.role === 'ASHA' ? WORKERS[1] : WORKERS[0];
                  setSelectedWorker(next);
                }}
                className="text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold px-2 py-1 rounded-lg transition-colors"
              >
                Switch
              </button>
            </div>

            <button
              onClick={handleReset}
              disabled={isResetting}
              className="w-full text-center text-[11px] text-slate-400 hover:text-red-600 py-1 transition-colors"
            >
              Clear Database Records
            </button>
          </div>
        </aside>

        {/* ========================================================= */}
        {/* 3. MAIN CONTENT WORKSPACE (Matching frame_004.png)         */}
        {/* ========================================================= */}
        <main className="flex-1 flex flex-col bg-white overflow-hidden relative">
          
          {/* Top Bar matching frame_004.png */}
          <header className="px-6 py-3.5 border-b border-slate-100 flex items-center justify-between bg-white shrink-0 z-10">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900">Orbita GPT</span>
              <span className="text-[10px] bg-slate-100 text-slate-600 font-medium px-2 py-0.5 rounded-md border border-slate-200/60">
                Plus • AAA-Setu v3.3
              </span>
            </div>

            <div className="flex items-center gap-2.5">
              <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-50 rounded-full text-xs border border-slate-200/80">
                <span
                  className={`w-2 h-2 rounded-full ${
                    wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-red-400'
                  }`}
                />
                <span className="text-slate-600 text-[11px] font-mono">
                  {wsConnected ? 'Live Broadcast <50ms' : 'Connecting WS...'}
                </span>
              </div>

              <button
                onClick={() => {
                  setActiveTab('chat');
                  setMessages([]);
                  setFloatingInput('');
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl shadow-2xs transition-all"
              >
                <span>New Chat</span>
                <Sparkles className="w-3.5 h-3.5 text-sky-300" />
              </button>
            </div>
          </header>

          {/* Emergency Alert Banner (If Critical Risk Detected) */}
          {criticalAlert && (
            <div className="bg-red-600 text-white px-6 py-2 shadow-xs flex items-center justify-between text-xs font-semibold shrink-0">
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-4 h-4 text-white shrink-0 animate-bounce" />
                <span>{criticalAlert}</span>
              </div>
              <button
                onClick={() => setCriticalAlert(null)}
                className="text-red-100 hover:text-white underline text-[11px] font-medium"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Scrollable Center Viewport */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 pb-32">
            {activeTab === 'chat' && (
              <UnifiedChatView
                messages={messages}
                selectedWorker={selectedWorker}
                isAuthenticated={isAuthenticated}
                activeOtp={activeOtp}
                onSendPreset={(presetText) => handleSendText(presetText)}
                onApproveQueueItem={handleApprove}
                currentlyPlayingAudio={currentlyPlayingAudio}
                onTogglePlayAudio={togglePlayAudio}
                onSwitchTab={(tab) => setActiveTab(tab)}
              />
            )}

            {activeTab === 'anmol' && (
              <AnmolQueuePanel
                queue={queue}
                onApprove={handleApprove}
                isApproving={isApproving}
              />
            )}

            {activeTab === 'poshan' && (
              <PoshanSyncPanel
                visits={poshanVisits}
                onSyncVisit={handleSyncPoshan}
              />
            )}

            {activeTab === 'register' && (
              <PaperRegister records={registerRecords} />
            )}
          </div>

          {/* ========================================================= */}
          {/* 4. SINGLE FLOATING INPUT PILL (EXACTLY frame_004.png)       */}
          {/* ========================================================= */}
          <div className="absolute bottom-4 left-0 right-0 px-4 md:px-6 pointer-events-none z-20 flex flex-col items-center">
            <div className="pointer-events-auto w-full max-w-3xl bg-white/95 backdrop-blur-md rounded-2xl border border-slate-200/90 shadow-xl p-2.5 px-4 flex items-center gap-3 transition-all">
              <Sparkles className="w-4 h-4 text-slate-400 shrink-0" />
              
              <input
                type="text"
                placeholder="Ask me anything... (e.g., RCH 999000104829 BP 142/92, swollen feet)"
                value={floatingInput}
                onChange={(e) => setFloatingInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                disabled={isFloatingSending}
                className="flex-1 bg-transparent border-none text-xs text-slate-800 placeholder-slate-400 focus:outline-none"
              />

              <div className="flex items-center gap-2 shrink-0">
                <select
                  value={selectedWorker.phone}
                  onChange={(e) => {
                    const w = WORKERS.find((p) => p.phone === e.target.value);
                    if (w) setSelectedWorker(w);
                  }}
                  className="bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-medium px-2 py-1.5 rounded-xl border border-slate-200 focus:outline-none cursor-pointer"
                  title="Select frontline worker"
                >
                  <option value="+919000012345">ASHA (Geeta)</option>
                  <option value="+919000098765">ANM (Kavita)</option>
                </select>

                <button
                  onClick={startFloatingVoice}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                    isFloatingRecording
                      ? 'bg-red-500 text-white animate-pulse shadow-md'
                      : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                  }`}
                  title="Voice Note"
                >
                  <Mic className="w-3.5 h-3.5" />
                  <span>{isFloatingRecording ? `${recordingSeconds}s` : 'Voice'}</span>
                </button>

                <button
                  onClick={() => handleSendText()}
                  disabled={!floatingInput.trim() && !isFloatingRecording}
                  className="w-8 h-8 rounded-full bg-slate-900 hover:bg-slate-800 text-white flex items-center justify-center shadow-xs transition-all disabled:opacity-40"
                  title="Send message"
                >
                  <Send className="w-3.5 h-3.5 ml-0.5" />
                </button>
              </div>
            </div>

            {/* Subtle Centra Disclaimer Text directly below pill (from frame_004.png) */}
            <p className="text-[10px] text-slate-400 mt-1.5 pointer-events-auto text-center">
              AAA-Setu may display field recommendations for ANM review. Strictly 100% synthetic records • MoHFW & MWCD guidelines
            </p>
          </div>

        </main>
      </div>
    </div>
  );
};

export default App;
