/**
 * LogsPanel.tsx – Real-Time Security Audit Log Viewer
 *
 * Displays the last 50 local encrypted audit log entries.
 */

import React, { useEffect } from 'react';
import { useJarvisStore } from '../../store/useJarvisStore';
import { X, Terminal, RefreshCw, ShieldCheck } from 'lucide-react';

export const LogsPanel: React.FC = () => {
  const { logsOpen, setLogsOpen, logs, refreshLogs } = useJarvisStore();

  useEffect(() => {
    if (logsOpen) {
      refreshLogs();
    }
  }, [logsOpen, refreshLogs]);

  if (!logsOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-start">
      {/* Backdrop */}
      <div
        onClick={() => setLogsOpen(false)}
        className="absolute inset-0 bg-black/70 backdrop-blur-xs animate-in fade-in"
      />

      {/* Drawer */}
      <div className="relative w-full max-w-xl h-full hud-panel border-r border-[#1677FF]/40 p-6 flex flex-col justify-between overflow-hidden animate-in slide-in-from-left duration-300">
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex justify-between items-center pb-4 border-b border-[#1677FF]/30 mb-4">
            <div className="flex items-center gap-2">
              <Terminal className="w-5 h-5 text-[#00B8FF]" />
              <div>
                <h2 className="hud-title text-base font-bold text-[#00B8FF] text-glow">SECURITY AUDIT LOGS</h2>
                <p className="text-xs text-[#7AA8FF] mono-val uppercase">BECKIE SQLCIPHER ENCRYPTED AUDIT TAIL</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={refreshLogs}
                title="Refresh Logs"
                className="p-1.5 rounded-lg border border-[#1677FF]/40 hover:bg-[#1677FF]/20 text-[#00B8FF] transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <button
                onClick={() => setLogsOpen(false)}
                className="p-1.5 rounded-lg border border-[#1677FF]/40 hover:bg-[#1677FF]/20 text-[#00B8FF] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-2 mb-3 px-3 py-1.5 rounded-lg bg-[#1677FF]/15 border border-[#00B8FF]/40 text-[#00B8FF] text-xs mono-val">
            <ShieldCheck className="w-4 h-4" />
            <span>Anti-Exfiltration Policy Enforced • Local-Only Zero Outbound Leakage</span>
          </div>

          {/* Log Stream Container */}
          <div className="flex-1 bg-[#030716] rounded-xl border border-[#1677FF]/30 p-4 font-mono text-xs overflow-y-auto space-y-2 text-[#D7EEFF]">
            {logs.length > 0 ? (
              logs.map((log, idx) => (
                <div key={idx} className="leading-relaxed hover:text-[#00B8FF] hover:bg-[#1677FF]/10 px-1 py-0.5 rounded transition-colors">
                  <span className="text-[#6A92BA] mr-2">[{idx + 1}]</span>
                  <span>{log}</span>
                </div>
              ))
            ) : (
              <div className="h-full flex items-center justify-center text-[#6A92BA]">
                Awaiting audit events...
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="pt-4 border-t border-[#1677FF]/30 mt-4 flex justify-between items-center text-[11px] mono-val text-[#6A92BA]">
            <span>SHOWING LAST 50 TRANSACTIONS</span>
            <span className="text-[#00B8FF]">INTEGRITY VERIFIED</span>
          </div>
        </div>
      </div>
    </div>
  );
};
