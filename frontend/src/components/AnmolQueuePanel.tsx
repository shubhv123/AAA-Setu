import React, { useState } from 'react';
import { Tablet, CheckCircle2, AlertOctagon, UserCheck, ShieldAlert, ArrowRight, Clock } from 'lucide-react';

interface QueueItem {
  queue_id: number;
  source_role: string;
  asha_worker_name: string;
  rch_id: string;
  mother_name?: string;
  village?: string;
  recorded_bp?: string;
  recorded_hb?: number;
  danger_signs_json: any;
  triage_severity: string;
  triage_action_hindi?: string;
  anm_approval_status: string;
  created_at: string;
}

interface AnmolQueuePanelProps {
  queue: QueueItem[];
  onApprove: (queueId: number) => Promise<void>;
  isApproving: number | null;
}

export const AnmolQueuePanel: React.FC<AnmolQueuePanelProps> = ({
  queue,
  onApprove,
  isApproving,
}) => {
  const [selectedAsha, setSelectedAsha] = useState<string>('ALL');

  // Extract unique ASHA names for filter pills
  const ashaList = Array.from(new Set(queue.map((q) => q.asha_worker_name).filter(Boolean)));

  const filteredQueue = queue.filter((item) => {
    if (selectedAsha === 'ALL') return true;
    return item.asha_worker_name === selectedAsha;
  });

  const parseSigns = (val: any): string[] => {
    if (Array.isArray(val)) return val;
    try {
      return JSON.parse(val || '[]');
    } catch {
      return [];
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4 flex flex-col h-full">
      {/* Tablet Header with Government Branding */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-teal-50 text-teal-700 rounded-lg">
            <Tablet className="w-5 h-5 text-teal-600" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-800">ANMOL Verification Queue</h2>
              <span className="text-[10px] bg-teal-100 text-teal-800 font-semibold px-2 py-0.5 rounded">
                Nurse Kavita (ANM)
              </span>
            </div>
            <p className="text-xs text-slate-500">MoHFW Frontline Tablet View • Sub-Centre / VHSND Camp</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200">
          <Clock className="w-3.5 h-3.5" />
          <span>Pending: <strong>{queue.filter((q) => q.anm_approval_status === 'PENDING_VERIFICATION').length}</strong></span>
        </div>
      </div>

      {/* ASHA-Wise Filter Pills */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold text-slate-600">Filter by Reporting ASHA:</span>
          <span className="text-[10px] text-slate-400">Zero typing: 1-tap verify</span>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setSelectedAsha('ALL')}
            className={`text-xs px-2.5 py-1 rounded-full font-medium transition-colors ${
              selectedAsha === 'ALL'
                ? 'bg-teal-700 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All Reports ({queue.length})
          </button>
          {ashaList.map((asha) => (
            <button
              key={asha}
              onClick={() => setSelectedAsha(asha)}
              className={`text-xs px-2.5 py-1 rounded-full font-medium transition-colors ${
                selectedAsha === asha
                  ? 'bg-teal-700 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {asha}
            </button>
          ))}
        </div>
      </div>

      {/* Queue Card Feed */}
      <div className="space-y-3 overflow-y-auto max-h-[460px] pr-1">
        {filteredQueue.length === 0 ? (
          <div className="text-center py-12 text-slate-400 text-xs">
            No verification cards in queue. Speak an ASHA home visit update to stage a record.
          </div>
        ) : (
          filteredQueue.map((item) => {
            const signs = parseSigns(item.danger_signs_json);
            const isCritical = item.triage_severity === 'CRITICAL_RED_SEAL';
            const isApproved = item.anm_approval_status === 'SYNCED_TO_RCH';

            return (
              <div
                key={item.queue_id}
                className={`rounded-xl border p-4 transition-all ${
                  isApproved
                    ? 'bg-slate-50/70 border-slate-200 opacity-80'
                    : isCritical
                    ? 'bg-red-50/40 border-red-300 shadow-sm ring-1 ring-red-200'
                    : 'bg-white border-slate-200 shadow-sm'
                }`}
              >
                {/* Card Header */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-900">
                        {item.mother_name || 'Sunita Devi (Synthetic)'}
                      </h3>
                      <span className="text-[11px] font-mono text-slate-500">
                        🆔 {item.rch_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                      <UserCheck className="w-3.5 h-3.5 text-blue-600" />
                      <span>Reported by: <strong>{item.asha_worker_name}</strong></span>
                      <span>•</span>
                      <span>{item.village || 'Kishanpur'}</span>
                    </div>
                  </div>

                  {/* Triage Badge */}
                  {isCritical ? (
                    <div className="flex items-center gap-1 bg-red-600 text-white text-[11px] font-bold px-2 py-1 rounded shadow-sm animate-pulse">
                      <AlertOctagon className="w-3.5 h-3.5" />
                      <span>🔴 CRITICAL: RED SEAL</span>
                    </div>
                  ) : item.triage_severity === 'URGENT' ? (
                    <div className="flex items-center gap-1 bg-amber-500 text-white text-[11px] font-bold px-2 py-1 rounded shadow-sm">
                      <ShieldAlert className="w-3.5 h-3.5" />
                      <span>⚠️ URGENT WATCH</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 bg-slate-100 text-slate-700 text-[11px] font-medium px-2 py-0.5 rounded">
                      <span>Normal ANC</span>
                    </div>
                  )}
                </div>

                {/* Pre-Filled Indicators (Zero Typing for Nurse Kavita) */}
                <div className="grid grid-cols-3 gap-2 bg-white/80 rounded-lg p-2.5 border border-slate-200/70 text-xs my-2.5">
                  <div>
                    <span className="text-[10px] text-slate-500 block uppercase">Last MCP Card BP</span>
                    <span className="font-semibold text-slate-800 text-xs">{item.recorded_bp || '142/92'}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block uppercase">Last MCP Card Hb</span>
                    <span className="font-semibold text-slate-800 text-xs">
                      {item.recorded_hb ? `${item.recorded_hb} g/dL` : '8.4 g/dL'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block uppercase">Danger Signs Today</span>
                    <span className="font-semibold text-red-600 text-[11px]">
                      {signs.length > 0 ? signs.join(', ') : 'None'}
                    </span>
                  </div>
                </div>

                {/* Hindi Triage Referral Advice */}
                {item.triage_action_hindi && (
                  <p className="text-xs text-slate-700 italic bg-slate-50 p-2 rounded border border-slate-100 mb-3">
                    💬 "{item.triage_action_hindi}"
                  </p>
                )}

                {/* Card Action / Approval Status */}
                <div className="flex items-center justify-between pt-1">
                  <div className="text-[11px] text-slate-400">
                    Source: <span className="font-medium text-slate-600">{item.source_role}</span>
                  </div>

                  {isApproved ? (
                    <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-semibold bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span>SYNCED TO RCH PORTAL</span>
                    </div>
                  ) : (
                    <button
                      onClick={() => onApprove(item.queue_id)}
                      disabled={isApproving === item.queue_id}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs px-4 py-2 rounded-lg flex items-center gap-1.5 shadow-sm transition-all hover:scale-102 disabled:opacity-50"
                    >
                      <span>Approve & Sync to RCH Portal</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

