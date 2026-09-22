"use client";

import React from "react";
import { SearchResultItem } from "../lib/types";
import { ExternalLink } from "lucide-react";

interface ComparisonTableProps {
  results: SearchResultItem[];
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({ results }) => {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="bg-slate-950/80 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
          <tr>
            <th className="py-3 px-4 font-semibold">Competitor</th>
            <th className="py-3 px-4 font-semibold">Domain</th>
            <th className="py-3 px-4 font-semibold">Type</th>
            <th className="py-3 px-4 font-semibold">Match Score</th>
            <th className="py-3 px-4 font-semibold">Reasoning</th>
            <th className="py-3 px-4 font-semibold">Verified</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60">
          {results.map((r) => (
            <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
              <td className="py-3 px-4 font-medium text-white">{r.competitor_name}</td>
              <td className="py-3 px-4">
                <a
                  href={r.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-emerald-400 hover:underline"
                >
                  <span>{r.domain}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </td>
              <td className="py-3 px-4">
                <span className="px-2 py-0.5 rounded text-xs font-medium uppercase tracking-wider bg-slate-800 border border-slate-700">
                  {r.competitor_type}
                </span>
              </td>
              <td className="py-3 px-4 font-semibold text-emerald-400">{Math.round(r.match_score)}%</td>
              <td className="py-3 px-4 text-xs text-slate-300 max-w-md">{r.reason}</td>
              <td className="py-3 px-4 text-xs text-slate-400">
                {new Date(r.verified_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
