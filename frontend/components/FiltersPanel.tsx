"use client";

import React from "react";
import { CompetitorType } from "../lib/types";

interface FiltersPanelProps {
  selectedTypes: CompetitorType[];
  onChange: (types: CompetitorType[]) => void;
}

export const FiltersPanel: React.FC<FiltersPanelProps> = ({ selectedTypes, onChange }) => {
  const options: { id: CompetitorType; label: string; description: string }[] = [
    { id: "direct", label: "Direct Competitors", description: "Same core offering & target audience" },
    { id: "indirect", label: "Indirect Competitors", description: "Adjacent solutions or substitute tools" },
    { id: "leader", label: "Market Leaders", description: "Category incumbents with massive footprint" },
  ];

  const toggleType = (type: CompetitorType) => {
    if (selectedTypes.includes(type)) {
      if (selectedTypes.length > 1) {
        onChange(selectedTypes.filter((t) => t !== type));
      }
    } else {
      onChange([...selectedTypes, type]);
    }
  };

  return (
    <div className="flex flex-wrap gap-2 pt-2">
      {options.map((opt) => {
        const isSelected = selectedTypes.includes(opt.id);
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => toggleType(opt.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
              isSelected
                ? "bg-emerald-950/70 border-emerald-600/70 text-emerald-300 shadow-sm"
                : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-300"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
};
