"use client";

import React, { useState, useEffect } from "react";
import { SearchForm } from "../components/SearchForm";
import { ResultsList } from "../components/ResultsList";
import { StreamingStatus } from "../components/StreamingStatus";
import { CreditIndicator } from "../components/CreditIndicator";
import { ScopeTag } from "../components/ScopeTag";
import { SearchCreateRequest, SearchResultItem, CompetitorType, LimitsResponse } from "../lib/types";
import { api } from "../lib/api";
import { Sparkles, ShieldCheck, Zap } from "lucide-react";

export default function HomePage() {
  const [limits, setLimits] = useState<LimitsResponse>({
    tier: "free",
    max_competitors: 10,
    default_competitors: 10,
    serpapi_max_calls: 3,
    firecrawl_candidate_multiplier: 2,
    firecrawl_use_extract: false,
    apify_enabled: false,
    embedding_provider: "local",
    llm_default_model: "claude-3-5-haiku-latest",
    llm_allow_escalation: false,
    credits_balance: 50,
    daily_quota_remaining: {},
  });

  const [loading, setLoading] = useState(false);
  const [searchStatus, setSearchStatus] = useState<"queued" | "running" | "completed" | "failed" | "clarification_needed">("completed");
  const [currentStage, setCurrentStage] = useState<string>("");
  const [shortfall, setShortfall] = useState(false);
  const [shortfallReason, setShortfallReason] = useState<string | undefined>();
  const [clarifyingQuestion, setClarifyingQuestion] = useState<string | null>(null);
  const [currentScope, setCurrentScope] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [filteredTypes, setFilteredTypes] = useState<CompetitorType[]>(["direct", "indirect", "leader"]);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    // Attempt to load limits on mount
    api.getLimits()
      .then((data) => setLimits(data))
      .catch(() => {
        // Fallback to default limits if unauthenticated / offline
      });
  }, []);

  const handleSearch = async (request: SearchCreateRequest) => {
    setLoading(true);
    setSearchStatus("queued");
    setCurrentStage("Initializing AI competitor search...");
    setShortfall(false);
    setShortfallReason(undefined);
    setErrorMessage(null);
    setResults([]);
    setClarifyingQuestion(null);
    if (request.competitor_types) {
      setFilteredTypes(request.competitor_types);
    }

    try {
      const searchRes = await api.createSearch(request);
      setSearchId(searchRes.id);
      setCurrentScope(searchRes.scope_override || "auto");
      setSearchStatus("running");
      setCurrentStage("Orchestrating 13-stage AI & live discovery pipeline...");

      // Connect to real-time Server-Sent Events stream
      const eventsUrl = api.getEventsUrl(searchRes.id);
      const eventSource = new EventSource(eventsUrl);

      // Polling fallback mechanism
      let isDone = false;
      const pollInterval = setInterval(async () => {
        if (isDone) {
          clearInterval(pollInterval);
          return;
        }
        try {
          const check = await api.getSearch(searchRes.id);
          if (check.status === "completed") {
            isDone = true;
            clearInterval(pollInterval);
            eventSource.close();
            setResults(check.results || []);
            setSearchStatus("completed");
            setCurrentStage(`Completed! Found ${check.results?.length || 0} verified competitors.`);
            setLoading(false);
            api.getLimits().then(setLimits).catch(() => {});
          } else if (check.status === "failed") {
            isDone = true;
            clearInterval(pollInterval);
            eventSource.close();
            setSearchStatus("failed");
            setErrorMessage(check.error_message || "Search pipeline encountered an error.");
            setCurrentStage("Search pipeline encountered an error.");
            setLoading(false);
          }
        } catch {
          // ignore transient poll error
        }
      }, 2500);

      eventSource.addEventListener("connected", () => {
        setCurrentStage("Connected to live search stream...");
      });

      eventSource.addEventListener("stage_started", (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          setCurrentStage(`[Stage ${payload.stage}/13] ${payload.message || payload.stage_name}`);
        } catch {}
      });

      eventSource.addEventListener("stage_completed", (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.stage === 1 && payload.data?.clarifying_question) {
            setClarifyingQuestion(payload.data.clarifying_question);
          }
        } catch {}
      });

      eventSource.addEventListener("shortfall", (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          setShortfall(true);
          setShortfallReason(payload.reason);
        } catch {}
      });

      eventSource.addEventListener("pipeline_error", (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.message) {
            setErrorMessage(payload.message);
          }
        } catch {}
      });

      eventSource.addEventListener("done", async () => {
        isDone = true;
        clearInterval(pollInterval);
        eventSource.close();
        try {
          const finalSearch = await api.getSearch(searchRes.id);
          setResults(finalSearch.results || []);
          setSearchStatus("completed");
          setCurrentStage(`Done! Verified ${finalSearch.results?.length || 0} competitors with zero hallucinations.`);
        } catch (err: any) {
          console.error("Failed to fetch final results", err);
        } finally {
          setLoading(false);
          api.getLimits().then(setLimits).catch(() => {});
        }
      });

      eventSource.addEventListener("error", async () => {
        // EventSource connection event
      });

    } catch (err: any) {
      setLoading(false);
      setSearchStatus("failed");
      setErrorMessage(err.message || "Failed to initiate search");
      setCurrentStage(err.message || "Failed to initiate search");
    }
  };

  const handleFeedback = async (resultId: string, type: "not_a_competitor") => {
    if (!searchId) return;
    try {
      await api.submitFeedback({
        search_id: searchId,
        search_result_id: resultId,
        feedback_type: type,
      });
    } catch (e) {
      console.error("Feedback error", e);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Hero Header */}
      <div className="text-center space-y-3 max-w-2xl mx-auto pt-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs font-medium text-slate-300">
          <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
          <span>Real-time competitor intelligence • Zero hallucinations</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Find Real, Verified Competitors Anywhere in the World
        </h1>
        <p className="text-sm text-slate-400">
          Enter any business name, URL, or description. Every competitor is extracted from live sources with verified URLs and timestamps.
        </p>

        {/* Plan & Credit Indicator */}
        <div className="flex justify-center pt-1">
          <CreditIndicator balance={limits.credits_balance} tier={limits.tier} />
        </div>
      </div>

      {/* Search Form */}
      <SearchForm
        maxCompetitors={limits.max_competitors}
        creditCostPerSearch={limits.tier === "paid" ? 5 : 1}
        loading={loading}
        clarifyingQuestion={clarifyingQuestion}
        onSearch={handleSearch}
        onAnswerClarification={() => setClarifyingQuestion(null)}
      />

      {/* Scope Tag if active */}
      {currentScope && (
        <div className="flex justify-center">
          <ScopeTag scope={currentScope} />
        </div>
      )}

      {/* Pipeline Status */}
      <div className="max-w-3xl mx-auto">
        <StreamingStatus
          status={searchStatus}
          currentStage={currentStage}
          shortfall={shortfall}
          shortfallReason={shortfallReason}
          error={errorMessage || undefined}
        />
      </div>

      {/* Empty State when completed with 0 results */}
      {searchStatus === "completed" && results.length === 0 && !loading && (
        <div className="max-w-md mx-auto p-6 rounded-2xl bg-slate-900/60 border border-slate-800 text-center space-y-2">
          <p className="font-semibold text-slate-200">No verified competitors found</p>
          <p className="text-xs text-slate-400">
            No active rivals met the strict live-source verification threshold for this query. Try adjusting your search query, location, or competitor type filters.
          </p>
        </div>
      )}

      {/* Results Section */}
      <div className="max-w-5xl mx-auto">
        <ResultsList
          results={results}
          filteredTypes={filteredTypes}
          onFeedback={handleFeedback}
        />
      </div>
    </div>
  );
}
