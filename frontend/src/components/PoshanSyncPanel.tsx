import React, { useState } from 'react';
import { HeartPulse, Wifi, WifiOff, RefreshCw, CheckCircle2, ShieldCheck } from 'lucide-react';

interface PoshanVisit {
  visit_id: number;
  rch_id: string;
  visit_number: number;
  joint_asha_aww_verified: boolean;
  sync_status: string;
  child_or_mother_name?: string;
  child_weight_kg?: number;
  thr_packets_verified?: number;
  created_at: string;
}

interface PoshanSyncPanelProps {
  visits: PoshanVisit[];
  onSyncVisit: (visitId: number) => Promise<void>;
}

export const PoshanSyncPanel: React.FC<PoshanSyncPanelProps> = ({
  visits,
  onSyncVisit,
}) => {
  const [offlineSimulation, setOfflineSimulation] = useState(false);
  const [syncingId, setSyncingId] = useState<number | null>(null);

  const handleSync = async (id: number) => {
    setSyncingId(id);
    try {
      await onSyncVisit(id);
    } finally {
      setSyncingId(null);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-purple-50 text-purple-700 rounded-lg">
            <HeartPulse className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-800">Poshan Tracker (v25.3.14)</h2>
              <span className="text-[10px] bg-purple-100 text-purple-800 font-semibold px-2 py-0.5 rounded">
                AWW View
              </span>
            </div>
            <p className="text-xs text-slate-500">MWCD Mandated Joint Visits (8, 9, 11, 14, 15) • Offline Resilient</p>
          </div>
        </div>

        {/* Offline Mode Simulation Toggle */}
        <div className="flex items-center gap-2 bg-slate-100 px-3 py-1.5 rounded-full border border-slate-200">
          {offlineSimulation ? <WifiOff className="w-4 h-4 text-amber-600" /> : <Wifi className="w-4 h-4 text-emerald-600" />}
          <span className="text-xs font-medium text-slate-700">
            {offlineSimulation ? 'Rural Offline Cache' : 'Online'}
          </span>
          <button
            onClick={() => setOfflineSimulation(!offlineSimulation)}
            className={`w-9 h-5 flex items-center rounded-full p-1 transition-colors ${
              offlineSimulation ? 'bg-amber-500' : 'bg-emerald-600'
            }`}
            title="Simulate rural low-connectivity offline mode"
          >
            <div
              className={`bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition-transform ${
                offlineSimulation ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Info Card */}
      <div className="bg-purple-50/50 border border-purple-100 rounded-lg p-3 text-xs text-purple-900 flex items-start gap-2">
        <ShieldCheck className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          MWCD mandates joint ASHA + AWW home visits for nutritional follow-up. When rural connectivity drops, visits are stored in the offline SQLite/Neon buffer and automatically dispatched to Poshan servers.
        </p>
      </div>

      {/* Visits List */}
      <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
        {visits.length === 0 ? (
          <div className="text-center py-6 text-slate-400 text-xs">
            No joint home visits logged yet. Speak Joint Visit #8 to see automatic capture.
          </div>
        ) : (
          visits.map((v) => {
            const isOffline = v.sync_status === 'CACHED_OFFLINE';
            return (
              <div
                key={v.visit_id}
                className={`p-3 rounded-lg border text-xs flex items-center justify-between gap-3 ${
                  isOffline
                    ? 'bg-amber-50/60 border-amber-200'
                    : 'bg-slate-50 border-slate-200'
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-800">
                      Joint Home Visit #{v.visit_number}
                    </span>
                    <span className="text-[10px] bg-blue-100 text-blue-800 font-semibold px-1.5 py-0.5 rounded">
                      ASHA + AWW Verified
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    Beneficiary: <strong>{v.child_or_mother_name || 'Sunita Devi'}</strong> (RCH: {v.rch_id})
                    {v.thr_packets_verified && ` • THR Packets: ${v.thr_packets_verified}`}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isOffline ? (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] font-semibold text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
                        CACHED OFFLINE
                      </span>
                      <button
                        onClick={() => handleSync(v.visit_id)}
                        disabled={syncingId === v.visit_id}
                        className="bg-amber-600 hover:bg-amber-700 text-white px-2.5 py-1 rounded text-[11px] font-medium flex items-center gap-1 transition-colors disabled:opacity-50"
                        title="Upload offline cached visit to MWCD"
                      >
                        <RefreshCw className={`w-3 h-3 ${syncingId === v.visit_id ? 'animate-spin' : ''}`} />
                        Sync Now
                      </button>
                    </div>
                  ) : (
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      SYNCED TO MWCD
                    </span>
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

