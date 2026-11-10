import React, { useState } from 'react';
import { Tablet, CheckCircle2, AlertOctagon, UserCheck, ShieldAlert, ArrowRight, Clock, ShieldCheck, Sparkles, AlertCircle, Info } from 'lucide-react';

interface QueueItem {
  queue_id: number;
  source_role: string;
  asha_worker_name: string;
  rch_id: string;
  beneficiary_name?: string;
  mother_name?: string;
  village?: string;
  recorded_bp?: string;
  bp_source?: string;
  recorded_hb?: number;
  weight_kg?: number;
  temperature_f?: number;
  danger_signs_json: any;
  supplies_or_meds?: any;
  dynamic_observations?: any;
  unmentioned_routine_checks?: any;
  priority_level: string;
  observed_indicators_summary?: string;
  recommended_next_steps?: any;
  triage_severity?: string;
  triage_action_hindi?: string;
  spoken_reply_native?: string;
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

  const parseArray = (val: any): any[] => {
    if (Array.isArray(val)) return val;
    try {
      return JSON.parse(val || '[]');
    } catch {
      return [];
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4 flex flex-col">
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
          <span className="text-xs font-semibold text-slate-600">Filter by Reporting Frontline Worker:</span>
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
      <div className="space-y-4 overflow-y-auto max-h-[520px] pr-1">
        {filteredQueue.length === 0 ? (
          <div className="text-center py-12 text-slate-400 text-xs">
            No verification cards in queue. Speak an ASHA home visit or clinic update to stage a record.
          </div>
        ) : (
          filteredQueue.map((item) => {
            const signs = parseArray(item.danger_signs_json);
            const supplies = parseArray(item.supplies_or_meds);
            const dynObs = parseArray(item.dynamic_observations);
            const unmentioned = parseArray(item.unmentioned_routine_checks);
            const nextSteps = parseArray(item.recommended_next_steps);

            const priority = item.priority_level || item.triage_severity || 'ROUTINE';
            const isUrgent = priority === 'URGENT_PHC_REFERRAL' || priority === 'CRITICAL_RED_SEAL';
            const isAttention = priority === 'ATTENTION_NEEDED' || priority === 'URGENT';
            const isApproved = item.anm_approval_status === 'SYNCED_TO_RCH';

            return (
              <div
                key={item.queue_id}
                className={`rounded-xl border p-4 transition-all space-y-3 ${
                  isApproved
                    ? 'bg-slate-50/70 border-slate-200 opacity-80'
                    : isUrgent
                    ? 'bg-red-50/30 border-red-300 shadow-sm ring-1 ring-red-200'
                    : isAttention
                    ? 'bg-amber-50/30 border-amber-300 shadow-sm'
                    : 'bg-white border-slate-200 shadow-sm'
                }`}
              >
                {/* Card Top: Beneficiary Info & Priority Badge */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-900">
                        {item.mother_name || item.beneficiary_name || 'Beneficiary'}
                      </h3>
                      <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                        🆔 {item.rch_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                      <UserCheck className="w-3.5 h-3.5 text-blue-600" />
                      <span>Reported by: <strong>{item.asha_worker_name}</strong></span>
                      <span>•</span>
                      <span>{item.village || 'Sub-Centre Area'}</span>
                    </div>
                  </div>

                  {/* Non-Diagnostic Priority Badge */}
                  {isUrgent ? (
                    <div className="flex items-center gap-1 bg-red-600 text-white text-[11px] font-bold px-2 py-1 rounded shadow-sm animate-pulse">
                      <AlertOctagon className="w-3.5 h-3.5" />
                      <span>🚨 URGENT PHC REFERRAL</span>
                    </div>
                  ) : isAttention ? (
                    <div className="flex items-center gap-1 bg-amber-500 text-white text-[11px] font-bold px-2 py-1 rounded shadow-sm">
                      <AlertCircle className="w-3.5 h-3.5" />
                      <span>⚠️ ATTENTION NEEDED</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 bg-emerald-600 text-white text-[11px] font-medium px-2 py-0.5 rounded">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>🟢 ROUTINE VISIT</span>
                    </div>
                  )}
                </div>

                {/* Dynamically Rendered Recorded Indicators (No empty placeholder boxes) */}
                <div className="flex flex-wrap gap-2 text-xs">
                  {item.recorded_bp && (
                    <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-800 border border-blue-200 px-2 py-1 rounded-md font-medium">
                      🩺 BP: <strong>{item.recorded_bp}</strong>
                      <span className="text-[10px] text-blue-600">({item.bp_source === 'MCP_CARD_HISTORY' ? 'MCP Card' : 'Live'})</span>
                    </span>
                  )}
                  {item.recorded_hb && (
                    <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-800 border border-indigo-200 px-2 py-1 rounded-md font-medium">
                      🩸 Hb: <strong>{item.recorded_hb} g/dL</strong>
                    </span>
                  )}
                  {item.weight_kg && (
                    <span className="inline-flex items-center gap-1 bg-slate-100 text-slate-800 border border-slate-200 px-2 py-1 rounded-md font-medium">
                      ⚖️ Weight: <strong>{item.weight_kg} kg</strong>
                    </span>
                  )}
                  {item.temperature_f && (
                    <span className="inline-flex items-center gap-1 bg-orange-50 text-orange-800 border border-orange-200 px-2 py-1 rounded-md font-medium">
                      🌡️ Temp: <strong>{item.temperature_f}°F</strong>
                    </span>
                  )}
                  {signs.length > 0 && (
                    <span className="inline-flex items-center gap-1 bg-red-50 text-red-700 border border-red-200 px-2 py-1 rounded-md font-medium">
                      ⚠️ Symptoms: {signs.join(', ')}
                    </span>
                  )}
                  {supplies.map((sup: string, i: number) => (
                    <span key={i} className="inline-flex items-center gap-1 bg-teal-50 text-teal-800 border border-teal-200 px-2 py-1 rounded-md text-[11px]">
                      💊 {sup}
                    </span>
                  ))}
                </div>

                {/* Dynamic Observations (Zero Information Loss) */}
                {dynObs.length > 0 && (
                  <div className="bg-slate-50/80 rounded-lg p-2.5 border border-slate-200/70 space-y-1.5">
                    <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">
                      Spoken Field Observations
                    </span>
                    <div className="grid grid-cols-1 gap-1">
                      {dynObs.map((obs: any, idx: number) => (
                        <div key={idx} className="flex items-start gap-1.5 text-xs text-slate-700">
                          <span className="text-teal-600 font-semibold shrink-0">• [{obs.category}]</span>
                          <span className="font-medium text-slate-800">{obs.field_label}:</span>
                          <span className="text-slate-600 italic">"{obs.spoken_value}"</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Dedicated AI Field Recommendation (Non-Diagnostic) Card */}
                <div className="bg-gradient-to-br from-white to-slate-50 rounded-lg p-3 border border-slate-200 shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-700">
                      <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                      <span>AI Field Recommendation (Non-Diagnostic)</span>
                    </div>
                    <span className="text-[9px] bg-slate-200/80 text-slate-600 px-1.5 py-0.5 rounded font-mono">
                      Decision Support — Verify with MO / ANM
                    </span>
                  </div>

                  {item.observed_indicators_summary && (
                    <p className="text-xs text-slate-700 bg-white p-2 rounded border border-slate-100">
                      <strong>Observation:</strong> {item.observed_indicators_summary}
                    </p>
                  )}

                  {nextSteps.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] uppercase font-semibold text-slate-500 block">Recommended Next Steps:</span>
                      <ul className="text-xs space-y-1 text-slate-700 pl-4 list-disc">
                        {nextSteps.map((step: string, sIdx: number) => (
                          <li key={sIdx}>{step}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Gentle Reminder for Unmentioned Checks */}
                  {unmentioned.length > 0 && (
                    <div className="flex items-center gap-1.5 text-[11px] text-amber-700 bg-amber-50/80 px-2 py-1 rounded border border-amber-200/60 mt-1">
                      <Info className="w-3.5 h-3.5 shrink-0 text-amber-600" />
                      <span>Not recorded in this interaction: <strong>{unmentioned.join(', ')}</strong> (schedule check at next VHSND camp).</span>
                    </div>
                  )}
                </div>

                {/* Hindi Voice Readout Message */}
                {(item.spoken_reply_native || item.triage_action_hindi) && (
                  <p className="text-xs text-slate-700 italic bg-slate-50 p-2 rounded border border-slate-100">
                    💬 "{item.spoken_reply_native || item.triage_action_hindi}"
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
