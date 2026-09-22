"use client";

import React from "react";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";

interface StreamingStatusProps {
  status: "queued" | "running" | "completed" | "failed" | "clarification_needed";
  currentStage?: string;
  shortfall?: boolean;
  shortfallReason?: string;
  error?: string;
}

export const StreamingStatus: React.FC<StreamingStatusProps> = ({
  status,
  currentStage,
  shortfall,
  shortfallReason,
  error,
}) => {
  if (status === "completed" && !shortfall && !error) {
    return null;
  }

  return (
    <div className="space-y-3">
      {/* Running / Queued Progress */}
      {(status === "queued" || status === "running") && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800 text-sm text-slate-300">
          <Loader2 className="w-5 h-5 text-emerald-400 animate-spin flex-shrink-0" />
          <div className="flex-1">
            <p className="font-medium text-slate-200">
              {status === "queued" ? "Queuing search job in priority lane..." : "Running competitor intelligence pipeline..."}
            </p>
            {currentStage && <p className="text-xs text-slate-400 mt-0.5">{currentStage}</p>}
          </div>
        </div>
      )}

      {/* Shortfall Notification */}
      {shortfall && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-950/40 border border-amber-800/60 text-sm text-amber-200">
          <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Shortfall Reported (Strict Verification)</p>
            <p className="text-xs text-amber-300/80 mt-1">
              {shortfallReason ||
                "Per core rules, fewer competitors were returned to guarantee that every result is verified live and authentic, without padding."}
            </p>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-rose-950/40 border border-rose-800/60 text-sm text-rose-200">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Search Encountered an Error</p>
            <p className="text-xs text-rose-300/80 mt-1">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
};
