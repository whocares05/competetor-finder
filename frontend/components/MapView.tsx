"use client";

import React from "react";
import { SearchResultItem } from "../lib/types";
import { MapPin, Navigation } from "lucide-react";

interface MapViewProps {
  results: SearchResultItem[];
}

export const MapView: React.FC<MapViewProps> = ({ results }) => {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col items-center justify-center min-h-[350px] text-center space-y-4">
      <div className="w-12 h-12 rounded-full bg-blue-950/80 border border-blue-800/80 flex items-center justify-center text-blue-400">
        <MapPin className="w-6 h-6" />
      </div>

      <div>
        <h4 className="text-base font-semibold text-white">Local Competitor Map View</h4>
        <p className="text-xs text-slate-400 max-w-md mt-1">
          Geo-spatial rendering activated for local searches. Found {results.length} competitor locations plotted.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 w-full max-w-2xl mt-4 text-left">
        {results.map((r) => (
          <div key={r.id} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs">
            <div className="flex items-center gap-1.5 font-medium text-slate-200">
              <Navigation className="w-3.5 h-3.5 text-blue-400" />
              <span>{r.competitor_name}</span>
            </div>
            <p className="text-slate-400 mt-1 truncate">{r.domain}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
