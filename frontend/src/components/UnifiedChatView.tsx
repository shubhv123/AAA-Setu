import React, { useRef, useEffect } from 'react';
import { 
  Sparkles, Play, Pause, CheckCircle2, AlertOctagon, 
  ShieldAlert, ArrowRight, Lock, Volume2, UserCheck, Activity,
  ChevronRight, HeartPulse, Tablet, FileSpreadsheet
} from 'lucide-react';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  audioUrl?: string;
  audioDurationSec?: number;
  extracted?: any;
  recommendation?: any;
  anmAlert?: any;
  otpPrompt?: {
    otp: string;
    phone: string;
  };
}

interface UnifiedChatViewProps {
  messages: ChatMessage[];
  selectedWorker: {
    phone: string;
    name: string;
    role: 'ASHA' | 'ANM';
    village: string;
  };
  isAuthenticated: boolean;
  activeOtp: string | null;
  onSendPreset: (text: string) => void;
  onApproveQueueItem?: (queueId: number) => void;
  currentlyPlayingAudio: string | null;
  onTogglePlayAudio: (url: string) => void;
  onSwitchTab: (tab: 'anmol' | 'poshan' | 'register') => void;
}

export const UnifiedChatView: React.FC<UnifiedChatViewProps> = ({
  messages,
  selectedWorker,
  isAuthenticated,
  activeOtp,
  onSendPreset,
  onApproveQueueItem,
  currentlyPlayingAudio,
  onTogglePlayAudio,
  onSwitchTab,
}) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // If there are no messages yet, display the exact Hero screen from frame_004.png
  if (messages.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center max-w-3xl mx-auto px-4 py-8 select-none">
        {/* Glowing Blue/Cyan Sphere matching frame_004.png */}
        <div className="relative">
          <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-blue-600 via-indigo-500 to-sky-400 shadow-xl shadow-blue-500/25 flex items-center justify-center animate-pulse" />
          <div className="absolute inset-0 rounded-full bg-blue-400/20 blur-xl -z-10" />
        </div>

        {/* Greeting Header */}
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight mt-5">
          Hi, there 👋
        </h2>
        <p className="text-sm text-slate-500 mt-1 text-center max-w-md">
          Tell us what you need, and we'll handle the rest.
        </p>

        {/* 3 Side-by-Side Cards matching frame_004.png */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 w-full mt-7">
          
          {/* Card 1: Dark Profile Card */}
          <div className="bg-slate-900 text-white rounded-2xl p-4 shadow-md flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-slate-800 text-white text-xs font-bold flex items-center justify-center border border-slate-700">
                    {selectedWorker.name.charAt(0)}
                  </div>
                  <div>
                    <p className="text-xs font-semibold leading-tight">{selectedWorker.name}</p>
                    <p className="text-[10px] text-slate-400">{selectedWorker.village}</p>
                  </div>
                </div>
                <span className="text-[10px] bg-blue-500 text-white font-medium px-2 py-0.5 rounded-full">
                  {selectedWorker.role}
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-3 leading-relaxed">
                Frontline healthcare worker. Dictate visit reports or upload voice notes in Indic languages.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
              <span>Status</span>
              <span className={isAuthenticated ? 'text-emerald-400 font-semibold' : 'text-amber-400'}>
                {isAuthenticated ? 'Authenticated 🟢' : 'OTP Needed 🔒'}
              </span>
            </div>
          </div>

          {/* Card 2: Field Guidelines Checklist */}
          <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-xs flex flex-col justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-800">Field Guidelines</p>
              <div className="mt-2.5 space-y-1.5 text-xs text-slate-600">
                <p className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                  <span>Only RCH ID is mandatory</span>
                </p>
                <p className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
                  <span>BP & Hb optional per visit</span>
                </p>
                <p className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500 shrink-0" />
                  <span>Zero loss on spoken details</span>
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
              <span>Protocol</span>
              <span className="text-blue-600 font-medium">NHM / MoHFW</span>
            </div>
          </div>

          {/* Card 3: Non-Diagnostic AI Triage */}
          <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-xs flex flex-col justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-800">What does AAA-Setu do?</p>
              <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                Evon v3.3 analyzes baseline history and observed symptoms to provide non-diagnostic risk alerts for ANM review.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
              <span>AI Engine</span>
              <span className="text-slate-700 font-medium">Gnani Evon v3.3</span>
            </div>
          </div>
        </div>

        {/* 4 Interactive Quick Action Pills matching frame_004.png */}
        <div className="flex items-center justify-center gap-2 flex-wrap mt-6">
          {!isAuthenticated ? (
            <button
              onClick={() => onSendPreset('Hi')}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-200/90 rounded-full text-xs text-slate-700 font-medium shadow-2xs hover:border-slate-300 transition-all"
            >
              <span className="text-emerald-600">👋</span>
              <span>Say "Hi" to Request Login OTP</span>
            </button>
          ) : (
            <>
              <button
                onClick={() =>
                  onSendPreset(
                    'Mata Sunita Devi, RCH ID 999000104829 ka home visit kiya. BP 142/92 mila aur dono pair me sujan hai.'
                  )
                }
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-200/90 rounded-full text-xs text-slate-700 font-medium shadow-2xs hover:border-slate-300 transition-all"
              >
                <span className="text-red-500">🚨</span>
                <span>High BP & Swelling (Red Seal)</span>
              </button>

              <button
                onClick={() =>
                  onSendPreset(
                    'RCH ID 999000104830, bache Priya ko 3 din se dast ho raha hai. ORS packet de diya aur maa ko samjhaya.'
                  )
                }
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-200/90 rounded-full text-xs text-slate-700 font-medium shadow-2xs hover:border-slate-300 transition-all"
              >
                <span className="text-amber-500">👶</span>
                <span>Child Diarrhea & Nutrition (No Vitals)</span>
              </button>

              <button
                onClick={() =>
                  onSendPreset(
                    'VHSND camp me RCH ID 999000104831 ka BP 130/80 aur Hb 8.4 g/dl record kiya, 30 IFA tablets di.'
                  )
                }
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-200/90 rounded-full text-xs text-slate-700 font-medium shadow-2xs hover:border-slate-300 transition-all"
              >
                <span className="text-teal-600">🩺</span>
                <span>ANM Direct VHSND Dictation</span>
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  // When messages exist, render a clean centered conversation thread
  return (
    <div className="max-w-3xl mx-auto w-full space-y-4 py-2">
      {/* Session Auth Bar (If OTP is active) */}
      {!isAuthenticated && activeOtp && (
        <div className="bg-amber-50 border border-amber-200/80 rounded-2xl p-3 flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2 text-xs text-amber-900 font-medium">
            <Lock className="w-4 h-4 text-amber-700 shrink-0" />
            <span>Active OTP issued for {selectedWorker.name}: <strong>{activeOtp}</strong></span>
          </div>
          <button
            onClick={() => onSendPreset(activeOtp)}
            className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-1 rounded-xl shadow-xs flex items-center gap-1 transition-colors"
          >
            <span>Auto-fill OTP</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Messages Stream */}
      {messages.map((m) => {
        const isUser = m.sender === 'user';

        return (
          <div
            key={m.id}
            className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1`}
          >
            {/* Message Bubble */}
            <div
              className={`rounded-2xl px-4 py-3 text-xs leading-relaxed max-w-[85%] shadow-xs transition-all ${
                isUser
                  ? 'bg-slate-900 text-white rounded-br-xs'
                  : 'bg-white border border-slate-200/80 text-slate-800 rounded-bl-xs'
              }`}
            >
              {/* If user sent an audio voice note */}
              {m.audioUrl && isUser && (
                <div className="flex items-center gap-2.5 py-1 mb-1">
                  <button
                    onClick={() => onTogglePlayAudio(m.audioUrl!)}
                    className="w-7 h-7 rounded-full bg-white/20 hover:bg-white/30 text-white flex items-center justify-center transition-colors"
                  >
                    {currentlyPlayingAudio === m.audioUrl ? (
                      <Pause className="w-3.5 h-3.5" />
                    ) : (
                      <Play className="w-3.5 h-3.5 ml-0.5" />
                    )}
                  </button>
                  <div className="text-[11px] text-slate-300 font-mono">
                    Voice Note ({m.audioDurationSec || 3}s)
                  </div>
                </div>
              )}

              {/* Message Text */}
              <p className="whitespace-pre-wrap">{m.text}</p>

              {/* Spoken TTS Audio Reply Player (Gnani Timbre v2.5) */}
              {m.audioUrl && !isUser && (
                <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between">
                  <button
                    onClick={() => onTogglePlayAudio(m.audioUrl!)}
                    className="flex items-center gap-2 text-[11px] text-teal-700 hover:text-teal-900 font-semibold bg-teal-50 hover:bg-teal-100/80 px-2.5 py-1 rounded-lg border border-teal-200/60 transition-colors"
                  >
                    {currentlyPlayingAudio === m.audioUrl ? (
                      <Pause className="w-3.5 h-3.5 text-teal-700" />
                    ) : (
                      <Play className="w-3.5 h-3.5 text-teal-700" />
                    )}
                    <span>Listen Spoken Reply (Timbre v2.5)</span>
                  </button>
                  <span className="text-[10px] text-slate-400 font-mono">Audio TTS</span>
                </div>
              )}

              {/* Extracted Vitals & Indicators Badges */}
              {m.extracted && !isUser && (
                <div className="mt-3 pt-2.5 border-t border-slate-100 space-y-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {m.extracted.rch_id && (
                      <span className="text-[10px] font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md font-semibold">
                        RCH: {m.extracted.rch_id}
                      </span>
                    )}
                    {m.extracted.bp_reading && (
                      <span className="text-[10px] bg-red-50 text-red-700 border border-red-200/60 px-2 py-0.5 rounded-md font-semibold">
                        BP: {m.extracted.bp_reading}
                      </span>
                    )}
                    {m.extracted.hb_g_dl && (
                      <span className="text-[10px] bg-blue-50 text-blue-700 border border-blue-200/60 px-2 py-0.5 rounded-md font-semibold">
                        Hb: {m.extracted.hb_g_dl} g/dL
                      </span>
                    )}
                    {m.extracted.weight_kg && (
                      <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200/60 px-2 py-0.5 rounded-md font-semibold">
                        Weight: {m.extracted.weight_kg} kg
                      </span>
                    )}
                  </div>

                  {/* Dynamic Non-Diagnostic Recommendation Box */}
                  {m.recommendation && (
                    <div className="bg-slate-50 border border-slate-200/70 rounded-xl p-2.5 space-y-1.5 mt-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-slate-700 uppercase tracking-wide">
                          AI Field Risk Indicator
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            m.recommendation.priority_level === 'URGENT_PHC_REFERRAL'
                              ? 'bg-red-100 text-red-800'
                              : m.recommendation.priority_level === 'ATTENTION_NEEDED'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-emerald-100 text-emerald-800'
                          }`}
                        >
                          {m.recommendation.priority_level}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600">
                        {m.recommendation.observed_indicators_summary}
                      </p>
                    </div>
                  )}

                  {/* 1-Tap ANM Approval Shortcut inside chat */}
                  {m.anmAlert && (
                    <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between">
                      <span className="text-[11px] text-slate-500">
                        Queue #{m.anmAlert.queue_id} logged to ANMOL
                      </span>
                      <button
                        onClick={() => onSwitchTab('anmol')}
                        className="text-xs bg-teal-600 hover:bg-teal-700 text-white font-semibold px-2.5 py-1 rounded-lg flex items-center gap-1 transition-colors shadow-xs"
                      >
                        <span>View in ANMOL Queue</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Timestamp */}
            <span className="text-[10px] text-slate-400 px-1">
              {m.timestamp}
            </span>
          </div>
        );
      })}

      <div ref={bottomRef} />
    </div>
  );
};

