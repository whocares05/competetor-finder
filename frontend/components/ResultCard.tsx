"use client";

import React, { useState } from "react";
import { ExternalLink, CheckCircle, ThumbsDown, RefreshCw } from "lucide-react";
import { SearchResultItem } from "../lib/types";

interface ResultCardProps {
  result: SearchResultItem;
  onFeedback?: (resultId: string, type: "not_a_competitor") => void;
  onReverify?: (resultId: string) => void;
}

export const ResultCard: React.FC<ResultCardProps> = ({ result, onFeedback, onReverify }) => {
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  const getTypeBadge = (type: string) => {
    switch (type) {
      case "direct":
        return "bg-rose-950/60 border-rose-800/60 text-rose-300";
      case "indirect":
        return "bg-amber-950/60 border-amber-800/60 text-amber-300";
      case "leader":
        return "bg-purple-950/60 border-purple-800/60 text-purple-300";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const handleFeedback = () => {
    if (onFeedback) {
      onFeedback(result.id, "not_a_competitor");
      setFeedbackSubmitted(true);
    }
  };

  return (
    <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800/80 hover:border-slate-700 transition-all flex flex-col justify-between gap-4">
      {/* Header: Name, domain, score */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-white hover:text-emerald-400 transition-colors">
              {result.competitor_name}
            </h3>
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-medium uppercase tracking-wider border ${getTypeBadge(
                result.competitor_type
              )}`}
            >
              {result.competitor_type}
            </span>
          </div>
          <a
            href={result.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-emerald-400 mt-1 transition-colors"
          >
            <span>{result.domain}</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {/* Match Score Badge */}
        <div className="flex flex-col items-end">
          <div className="flex items-baseline gap-0.5">
            <span className="text-lg font-bold text-emerald-400">{Math.round(result.match_score)}</span>
            <span className="text-xs text-slate-500">/100</span>
          </div>
          <span className="text-[10px] text-slate-400">Match score</span>
        </div>
      </div>

      {/* Reason */}
      <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/50 p-3 rounded-lg border border-slate-800/50">
        {result.reason}
      </p>

      {/* Footer: Live source, verification timestamp, feedback buttons */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs text-slate-400">
        <div className="flex items-center gap-1.5">
          <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
          <span>Verified live: {new Date(result.verified_at).toLocaleDateString()}</span>
        </div>

        <div className="flex items-center gap-2">
          {onReverify && (
            <button
              type="button"
              onClick={() => onReverify(result.id)}
              className="flex items-center gap-1 px-2 py-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
              title="Force live re-verification"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Re-verify</span>
            </button>
          )}

          {feedbackSubmitted ? (
            <span className="text-[11px] text-slate-500">Feedback received</span>
          ) : (
            <button
              type="button"
              onClick={handleFeedback}
              className="flex items-center gap-1 px-2 py-1 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
              title="Flag as not a competitor"
            >
              <ThumbsDown className="w-3 h-3" />
              <span>Not a competitor</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
