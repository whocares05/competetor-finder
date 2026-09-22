"use client";

import React from "react";
import { Coins, Zap, ShieldCheck } from "lucide-react";

interface CreditIndicatorProps {
  balance: number;
  tier: string;
}

export const CreditIndicator: React.FC<CreditIndicatorProps> = ({ balance, tier }) => {
  const isPaid = tier.toLowerCase() === "paid";

  return (
    <div className="flex items-center gap-2.5">
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-sm font-medium text-slate-200">
        <Coins className="w-4 h-4 text-amber-400" />
        <span>{balance}</span>
        <span className="text-xs text-slate-400">credits</span>
      </div>

      <div
        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider border ${
          isPaid
            ? "bg-purple-950/60 border-purple-700/60 text-purple-300"
            : "bg-slate-800/50 border-slate-700/60 text-slate-400"
        }`}
      >
        {isPaid ? <Zap className="w-3.5 h-3.5 text-purple-400" /> : <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />}
        <span>{tier} plan</span>
      </div>
    </div>
  );
};
