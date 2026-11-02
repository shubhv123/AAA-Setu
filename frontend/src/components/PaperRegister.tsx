import React, { useState } from 'react';
import { FileSpreadsheet, MessageSquare, Copy, Check, Printer } from 'lucide-react';

interface PaperRegisterRecord {
  record_id: number;
  record_date: string;
  rch_id: string;
  mother_name: string;
  village: string;
  worker_name: string;
  bp?: string;
  hb?: number;
  danger_signs?: string;
  referral_action?: string;
  whatsapp_row_text: string;
  created_at: string;
}

interface PaperRegisterProps {
  records: PaperRegisterRecord[];
}

export const PaperRegister: React.FC<PaperRegisterProps> = ({ records }) => {
  const [activeTab, setActiveTab] = useState<'table' | 'whatsapp'>('whatsapp');
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const handleCopy = (text: string, id: number) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handlePrint = () => {
    window.print();
  };

  const latestRecord = records[0];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-emerald-50 text-emerald-700 rounded-lg">
            <FileSpreadsheet className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-800">Physical Audit & WhatsApp Bridge</h2>
            <p className="text-xs text-slate-500">Eliminates Mental Math for Mandatory Paper Register Inspections</p>
          </div>
        </div>

        {/* Tab Switcher & Print Button */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-100 p-1 rounded-lg text-xs">
            <button
              onClick={() => setActiveTab('whatsapp')}
              className={`px-3 py-1 rounded-md font-medium flex items-center gap-1.5 transition-all ${
                activeTab === 'whatsapp' ? 'bg-white shadow-sm text-emerald-700 font-semibold' : 'text-slate-600'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              WhatsApp Row
            </button>
            <button
              onClick={() => setActiveTab('table')}
              className={`px-3 py-1 rounded-md font-medium flex items-center gap-1.5 transition-all ${
                activeTab === 'table' ? 'bg-white shadow-sm text-blue-700 font-semibold' : 'text-slate-600'
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              Register Table
            </button>
          </div>

          <button
            onClick={handlePrint}
            className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
            title="Print Physical Audit Register Sheet"
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* WhatsApp Message Preview View */}
      {activeTab === 'whatsapp' && (
        <div className="space-y-3">
          {latestRecord ? (
            <div className="bg-emerald-50/60 border border-emerald-200 rounded-xl p-4 relative">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-emerald-800 flex items-center gap-1">
                  <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />
                  Latest WhatsApp Summary Row (Geeta's Phone)
                </span>
                <button
                  onClick={() => handleCopy(latestRecord.whatsapp_row_text, latestRecord.record_id)}
                  className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 hover:text-emerald-900 bg-white px-2.5 py-1 rounded-md border border-emerald-200 shadow-xs transition-colors"
                >
                  {copiedId === latestRecord.record_id ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy for Register</span>
                    </>
                  )}
                </button>
              </div>

              <pre className="text-xs font-mono text-slate-800 whitespace-pre-wrap leading-relaxed bg-white/80 p-3 rounded-lg border border-emerald-100 shadow-inner">
                {latestRecord.whatsapp_row_text}
              </pre>

              <p className="text-[11px] text-emerald-900 mt-2 italic">
                💡 ASHA can write this row directly into her physical audit register in 15 seconds at day-end without manual calculations.
              </p>
            </div>
          ) : (
            <div className="text-center py-6 text-slate-400 text-xs">
              No WhatsApp summaries generated yet. Run a voice check-in to see instant formatting.
            </div>
          )}
        </div>
      )}

      {/* Printable Physical Register Table View */}
      {activeTab === 'table' && (
        <div className="overflow-x-auto border border-slate-200 rounded-lg">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
              <tr>
                <th className="p-2 border-r border-slate-200">Date</th>
                <th className="p-2 border-r border-slate-200">RCH ID</th>
                <th className="p-2 border-r border-slate-200">Mother Name</th>
                <th className="p-2 border-r border-slate-200">Village</th>
                <th className="p-2 border-r border-slate-200">Worker</th>
                <th className="p-2 border-r border-slate-200">BP</th>
                <th className="p-2 border-r border-slate-200">Hb</th>
                <th className="p-2 border-r border-slate-200">Danger Signs</th>
                <th className="p-2">Referral / Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {records.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-4 text-center text-slate-400 text-xs">
                    No physical register rows logged.
                  </td>
                </tr>
              ) : (
                records.map((r) => (
                  <tr key={r.record_id} className="hover:bg-slate-50 transition-colors">
                    <td className="p-2 font-mono text-[11px] border-r border-slate-100">{r.record_date}</td>
                    <td className="p-2 font-mono text-[11px] font-semibold text-blue-700 border-r border-slate-100">{r.rch_id}</td>
                    <td className="p-2 font-medium text-slate-900 border-r border-slate-100">{r.mother_name}</td>
                    <td className="p-2 text-slate-600 border-r border-slate-100">{r.village}</td>
                    <td className="p-2 text-slate-600 border-r border-slate-100">{r.worker_name}</td>
                    <td className="p-2 font-semibold text-slate-800 border-r border-slate-100">{r.bp || '—'}</td>
                    <td className="p-2 font-semibold text-slate-800 border-r border-slate-100">{r.hb ? `${r.hb} g/dL` : '—'}</td>
                    <td className="p-2 text-red-600 font-medium border-r border-slate-100">{r.danger_signs || 'None'}</td>
                    <td className="p-2 text-slate-700 text-[11px]">{r.referral_action || 'Normal ANC'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

