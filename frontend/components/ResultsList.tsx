"use client";

import React, { useState } from "react";
import { SearchResultItem, CompetitorType } from "../lib/types";
import { ResultCard } from "./ResultCard";
import { ComparisonTable } from "./ComparisonTable";
import { MapView } from "./MapView";
import { LayoutList, Table, Map, Download } from "lucide-react";

interface ResultsListProps {
  results: SearchResultItem[];
  filteredTypes: CompetitorType[];
  onFeedback?: (resultId: string, type: "not_a_competitor") => void;
  onReverify?: (resultId: string) => void;
}

export const ResultsList: React.FC<ResultsListProps> = ({
  results,
  filteredTypes,
  onFeedback,
  onReverify,
}) => {
  const [viewMode, setViewMode] = useState<"cards" | "table" | "map">("cards");

  const displayedResults = results.filter((r) =>
    filteredTypes.includes(r.competitor_type)
  );

  const exportCSV = () => {
    if (displayedResults.length === 0) return;
    const headers = ["Competitor Name", "Domain", "Type", "Match Score", "Reason", "Source URL", "Verified At"];
    const rows = displayedResults.map((r) => [
      `"${r.competitor_name}"`,
      `"${r.domain}"`,
      `"${r.competitor_type}"`,
      r.match_score,
      `"${r.reason.replace(/"/g, '""')}"`,
      `"${r.source_url}"`,
      `"${r.verified_at}"`,
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `competitors_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (results.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {/* Action bar: View switches & Export */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <span className="text-sm font-medium text-slate-300">
          Showing {displayedResults.length} verified {displayedResults.length === 1 ? "competitor" : "competitors"}
        </span>

        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setViewMode("cards")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                viewMode === "cards" ? "bg-slate-800 text-white font-medium" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <LayoutList className="w-3.5 h-3.5" />
              <span>Cards</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                viewMode === "table" ? "bg-slate-800 text-white font-medium" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Table className="w-3.5 h-3.5" />
              <span>Table</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("map")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                viewMode === "map" ? "bg-slate-800 text-white font-medium" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Map className="w-3.5 h-3.5" />
              <span>Map</span>
            </button>
          </div>

          <button
            type="button"
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Main View Renderer */}
      {viewMode === "cards" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {displayedResults.map((result) => (
            <ResultCard
              key={result.id}
              result={result}
              onFeedback={onFeedback}
              onReverify={onReverify}
            />
          ))}
        </div>
      )}

      {viewMode === "table" && <ComparisonTable results={displayedResults} />}

      {viewMode === "map" && <MapView results={displayedResults} />}
    </div>
  );
};
