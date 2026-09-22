"use client";

import React from "react";
import { Globe, MapPin, Flag } from "lucide-react";

interface ScopeTagProps {
  scope: string;
  isOverride?: boolean;
}

export const ScopeTag: React.FC<ScopeTagProps> = ({ scope, isOverride }) => {
  const normalized = scope.toLowerCase();

  const getBadge = () => {
    switch (normalized) {
      case "local":
        return {
          icon: <MapPin className="w-3.5 h-3.5 text-blue-400" />,
          label: "Local Scope",
          bg: "bg-blue-950/60 text-blue-300 border-blue-800/60",
        };
      case "national":
        return {
          icon: <Flag className="w-3.5 h-3.5 text-amber-400" />,
          label: "National Scope",
          bg: "bg-amber-950/60 text-amber-300 border-amber-800/60",
        };
      case "global":
      default:
        return {
          icon: <Globe className="w-3.5 h-3.5 text-emerald-400" />,
          label: "Global Scope",
          bg: "bg-emerald-950/60 text-emerald-300 border-emerald-800/60",
        };
    }
  };

  const badge = getBadge();

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${badge.bg}`}
    >
      {badge.icon}
      <span>{badge.label}</span>
      {isOverride && <span className="text-[10px] opacity-75">(Override)</span>}
    </span>
  );
};
