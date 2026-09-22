"use client";

import React, { useState } from "react";
import { Search, MapPin, Sparkles, SlidersHorizontal, HelpCircle } from "lucide-react";
import { CompetitorType, ScopeOverride, SearchCreateRequest } from "../lib/types";
import { FiltersPanel } from "./FiltersPanel";

interface SearchFormProps {
  maxCompetitors: number;
  creditCostPerSearch: number;
  loading: boolean;
  clarifyingQuestion?: string | null;
  onSearch: (request: SearchCreateRequest) => void;
  onAnswerClarification?: (answer: string) => void;
}

export const SearchForm: React.FC<SearchFormProps> = ({
  maxCompetitors,
  creditCostPerSearch,
  loading,
  clarifyingQuestion,
  onSearch,
  onAnswerClarification,
}) => {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [numCompetitors, setNumCompetitors] = useState(10);
  const [scopeOverride, setScopeOverride] = useState<ScopeOverride>("auto");
  const [competitorTypes, setCompetitorTypes] = useState<CompetitorType[]>([
    "direct",
    "indirect",
    "leader",
  ]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [clarificationAnswer, setClarificationAnswer] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    onSearch({
      query: query.trim(),
      location: location.trim() || undefined,
      num_competitors: Math.min(numCompetitors, maxCompetitors),
      scope_override: scopeOverride,
      competitor_types: competitorTypes,
    });
  };

  const handleClarificationSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const answer = clarificationAnswer.trim();
    if (!answer) return;

    if (onAnswerClarification) {
      onAnswerClarification(answer);
    }

    // Combine current query with clarifying answer and trigger search
    const baseQuery = query.trim() || answer;
    const combinedQuery = baseQuery.toLowerCase().includes(answer.toLowerCase())
      ? baseQuery
      : `${baseQuery} (${answer})`;

    setQuery(combinedQuery);
    setClarificationAnswer("");

    onSearch({
      query: combinedQuery,
      location: location.trim() || undefined,
      num_competitors: Math.min(numCompetitors, maxCompetitors),
      scope_override: scopeOverride,
      competitor_types: competitorTypes,
    });
  };

  return (
    <div className="w-full max-w-3xl mx-auto space-y-4">
      {/* Clarifying Question Modal / Inline Box */}
      {clarifyingQuestion && (
        <div className="p-5 rounded-2xl bg-amber-950/40 border border-amber-800/80 space-y-3 shadow-xl">
          <div className="flex items-center gap-2 text-amber-300 font-semibold text-sm">
            <HelpCircle className="w-5 h-5 flex-shrink-0" />
            <span>Clarification Needed to Ensure Verified Accuracy</span>
          </div>
          <p className="text-sm text-amber-100">{clarifyingQuestion}</p>
          <form onSubmit={handleClarificationSubmit} className="flex gap-2 pt-2">
            <input
              type="text"
              value={clarificationAnswer}
              onChange={(e) => setClarificationAnswer(e.target.value)}
              placeholder="Your clarifying answer..."
              className="flex-1 px-3 py-2 rounded-lg bg-slate-950/80 border border-amber-700/60 text-sm text-white focus:outline-none focus:border-amber-400"
            />
            <button
              type="submit"
              onClick={handleClarificationSubmit}
              disabled={loading || !clarificationAnswer.trim()}
              className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-sm rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading ? "Searching..." : "Submit Answer"}
            </button>
          </form>
        </div>
      )}

      {/* Main Search Input Form */}
      <form onSubmit={handleSubmit} className="glass-panel p-5 rounded-2xl shadow-2xl space-y-4">
        {/* Main query input */}
        <div className="relative">
          <Search className="w-5 h-5 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter business name, website URL (e.g. linear.app), or description..."
            className="w-full pl-12 pr-4 py-3.5 rounded-xl glass-input text-white placeholder-slate-500 text-base"
            required
          />
        </div>

        {/* Location & Advanced Toggle */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <MapPin className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="City, region, or country (optional - auto-inferred)"
              className="w-full pl-10 pr-4 py-2.5 rounded-xl glass-input text-sm text-white placeholder-slate-500"
            />
          </div>

          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className={`flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium border transition-colors ${
              showAdvanced
                ? "bg-slate-800 border-slate-700 text-slate-200"
                : "border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            <SlidersHorizontal className="w-4 h-4" />
            <span>Options</span>
          </button>
        </div>

        {/* Advanced Filters Panel */}
        {showAdvanced && (
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-4 text-xs">
            {/* Competitors Count Slider */}
            <div className="space-y-2">
              <div className="flex justify-between font-medium text-slate-300">
                <span>Number of competitors: {numCompetitors}</span>
                <span className="text-slate-500">Tier Max: {maxCompetitors}</span>
              </div>
              <input
                type="range"
                min={3}
                max={maxCompetitors}
                value={numCompetitors}
                onChange={(e) => setNumCompetitors(Number(e.target.value))}
                className="w-full accent-emerald-500 bg-slate-800 rounded-lg cursor-pointer"
              />
            </div>

            {/* Scope Override Selection */}
            <div className="space-y-1.5">
              <span className="font-medium text-slate-300">Geographic Scope Override:</span>
              <div className="grid grid-cols-4 gap-2">
                {(["auto", "local", "national", "global"] as ScopeOverride[]).map((scope) => (
                  <button
                    key={scope}
                    type="button"
                    onClick={() => setScopeOverride(scope)}
                    className={`py-1.5 rounded-lg text-xs font-medium uppercase border transition-all ${
                      scopeOverride === scope
                        ? "bg-emerald-950 border-emerald-600 text-emerald-300"
                        : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-300"
                    }`}
                  >
                    {scope}
                  </button>
                ))}
              </div>
            </div>

            {/* Competitor Classification Filters */}
            <div className="space-y-1.5">
              <span className="font-medium text-slate-300">Filter Classification Types:</span>
              <FiltersPanel selectedTypes={competitorTypes} onChange={setCompetitorTypes} />
            </div>
          </div>
        )}

        {/* Action bar with Credit Cost and Submit */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
          <span className="text-xs text-slate-400">
            Estimated cost: <strong className="text-slate-200">{creditCostPerSearch} credits</strong>
          </span>

          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all shadow-lg shadow-emerald-950 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Sparkles className="w-4 h-4" />
            <span>{loading ? "Searching Live Web..." : "Find Competitors"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
