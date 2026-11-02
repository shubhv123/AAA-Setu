import React, { useState, useEffect } from 'react';
import confetti from 'canvas-confetti';
import { ShieldAlert, RefreshCw, Activity, Heart, AlertOctagon, CheckCircle2 } from 'lucide-react';
import { VoiceSimulator } from './components/VoiceSimulator';
import { AnmolQueuePanel } from './components/AnmolQueuePanel';
import { PoshanSyncPanel } from './components/PoshanSyncPanel';
import { PaperRegister } from './components/PaperRegister';

export const App: React.FC = () => {
  const [queue, setQueue] = useState<any[]>([]);
  const [poshanVisits, setPoshanVisits] = useState<any[]>([]);
  const [registerRecords, setRegisterRecords] = useState<any[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isApproving, setIsApproving] = useState<number | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [criticalAlert, setCriticalAlert] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);

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

  useEffect(() => {
    fetchAllData();

    // Setup Real-time WebSocket Listener
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let socket: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWs = () => {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setWsConnected(true);
        console.log('Connected to AAA-Setu WebSocket Broadcaster');
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { event: eventType, data } = payload;

          if (eventType === 'voice_processed') {
            if (data?.triage?.severity === 'CRITICAL_RED_SEAL') {
              setCriticalAlert(
                `🚨 CRITICAL RED SEAL ALERT: Pre-Eclampsia detected for ${data.extracted?.beneficiary_name || 'Sunita Devi'}! Immediate PHC Referral Dispatched.`
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
            fetchAllData();
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
        console.warn('WebSocket error, retrying...', err);
        socket?.close();
      };
    };

    connectWs();

    return () => {
      clearTimeout(reconnectTimeout);
      socket?.close();
    };
  }, []);

  // One-Tap Approval by ANM
  const handleApprove = async (queueId: number) => {
    setIsApproving(queueId);
    try {
      const res = await fetch(`/api/anmol/approve/${queueId}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to approve');

      // Trigger celebratory confetti for 1-tap success
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.6 },
      });

      await fetchAllData();
    } catch (e: any) {
      setApiError(e.message);
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
      setApiError(e.message);
    }
  };

  // Reset Demo to Baseline
  const handleReset = async () => {
    setIsResetting(true);
    try {
      const res = await fetch('/api/reset', { method: 'POST' });
      if (res.ok) {
        setCriticalAlert(null);
        setApiError(null);
        await fetchAllData();
      }
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="bg-slate-900 text-white shadow-md border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-tr from-blue-600 to-teal-500 rounded-xl shadow-md">
              <Activity className="w-5 h-5 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight">AAA-Setu (ANMOL-Sahayak)</h1>
                <span className="text-[10px] bg-blue-500/20 text-blue-300 font-semibold px-2 py-0.5 rounded-full border border-blue-400/30">
                  AI Sahayak Mandatory Disclosure
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Gnani Artha Stack: Prisma v3.0 • Evon v3.3 • Timbre v2.5 • Neon PostgreSQL
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Real-time WebSocket Status Indicator */}
            <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-800/80 rounded-full text-xs border border-slate-700">
              <span
                className={`w-2 h-2 rounded-full ${
                  wsConnected ? 'bg-emerald-400 animate-ping' : 'bg-red-400'
                }`}
              />
              <span className="text-slate-300 text-[11px] font-mono">
                {wsConnected ? 'Live Broadcast <50ms' : 'Connecting WS...'}
              </span>
            </div>

            {/* 1-Click Reset Button for Judges */}
            <button
              onClick={handleReset}
              disabled={isResetting}
              className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white px-3 py-1.5 rounded-lg border border-slate-700 transition-colors disabled:opacity-50"
              title="Reset database to synthetic baseline seed data"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
              <span>Reset Demo State</span>
            </button>
          </div>
        </div>
      </header>

      {/* Critical Red-Seal Emergency Alert Banner */}
      {criticalAlert && (
        <div className="bg-red-600 text-white px-4 py-2.5 shadow-md flex items-center justify-between animate-bounce">
          <div className="max-w-7xl mx-auto flex items-center gap-2 text-xs font-bold w-full">
            <AlertOctagon className="w-4 h-4 shrink-0" />
            <span>{criticalAlert}</span>
          </div>
          <button
            onClick={() => setCriticalAlert(null)}
            className="text-xs text-red-200 hover:text-white font-semibold underline px-2"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Split-Screen Grid Layout */}
      <main className="max-w-7xl mx-auto px-4 py-5 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column (5 Cols): Voice Simulator & Physical Audit Register */}
        <div className="lg:col-span-5 space-y-5">
          <VoiceSimulator
            onSessionProcessed={() => fetchAllData()}
            apiError={apiError}
            setApiError={setApiError}
            isProcessing={isProcessing}
            setIsProcessing={setIsProcessing}
          />
          <PaperRegister records={registerRecords} />
        </div>

        {/* Right Column (7 Cols): ANM Tablet View (ANMOL Queue) & Poshan Sync */}
        <div className="lg:col-span-7 space-y-5">
          <AnmolQueuePanel
            queue={queue}
            onApprove={handleApprove}
            isApproving={isApproving}
          />
          <PoshanSyncPanel
            visits={poshanVisits}
            onSyncVisit={handleSyncPoshan}
          />
        </div>
      </main>

      {/* Footer Compliance Notice */}
      <footer className="bg-slate-900/90 text-slate-400 border-t border-slate-800 text-[11px] py-2.5 px-4 text-center">
        <p>
          🇮🇳 Built for the <strong>Gnani.ai Great Indian AI Internship Challenge</strong>. Strictly 100% synthetic healthcare records adhering to MoHFW & MWCD public health guidelines.
        </p>
      </footer>
    </div>
  );
};

export default App;

