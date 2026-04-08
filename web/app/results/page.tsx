"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { getOptimizeStatus, optimizeResume } from "../../lib/api";
import { useAtsSessionStore } from "../../store/atsSession";

const verdictLabel: Record<string, string> = {
  reject: "Reject",
  borderline: "Borderline",
  strong: "Strong",
};

export default function ResultsPage() {
  const router = useRouter();
  const {
    resumeFile,
    scoreResult,
    getAnalyzeInput,
    setOptimizedResume,
    setOptimizeJobId,
    optimizeJobId,
  } = useAtsSessionStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const score = scoreResult?.score ?? 0;

  const ringStyle = useMemo(
    () => ({
      background: `conic-gradient(#047857 ${Math.max(0, Math.min(100, score)) * 3.6}deg, #d1d5db 0deg)`,
    }),
    [score]
  );

  if (!scoreResult || !resumeFile) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-slate-700">No score session found. Start from the home page.</p>
        <button className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-white" onClick={() => router.push("/")}>
          Go Home
        </button>
      </main>
    );
  }

  async function handleOptimize() {
    if (!resumeFile || !scoreResult) {
      setError("Missing resume or score context. Please re-run analysis.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const queued = await optimizeResume(resumeFile, scoreResult, getAnalyzeInput());
      setOptimizeJobId(queued.job_id);

      let done = false;
      while (!done) {
        const status = await getOptimizeStatus(queued.job_id);
        if (status.status === "failed") {
          throw new Error(status.error_message || "Optimize job failed");
        }
        if (status.status === "completed" && status.result) {
          setOptimizedResume(status.result);
          done = true;
          router.push("/optimize");
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1200));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to optimize resume");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-6 py-10">
      <h1 className="text-3xl font-bold">ATS Score Results</h1>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-300 bg-white p-6">
          <div className="mx-auto flex h-56 w-56 items-center justify-center rounded-full" style={ringStyle}>
            <div className="flex h-40 w-40 flex-col items-center justify-center rounded-full bg-white">
              <p className="text-5xl font-bold">{score}</p>
              <p className="text-xs uppercase tracking-wider text-slate-500">out of 100</p>
            </div>
          </div>
          <div className="mt-4 flex justify-center">
            <span className="rounded-full bg-slate-900 px-4 py-1 text-sm font-semibold text-white">
              {verdictLabel[scoreResult.verdict] ?? scoreResult.verdict}
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-300 bg-white p-6">
          <h2 className="text-lg font-semibold">Section Breakdown</h2>
          {Object.entries(scoreResult.breakdown).map(([key, value]) => (
            <div key={key} className="mt-4">
              <div className="mb-1 flex justify-between text-sm">
                <span className="capitalize">{key}</span>
                <span>{value}%</span>
              </div>
              <div className="h-2 rounded bg-slate-200">
                <div className="h-2 rounded bg-emerald-600" style={{ width: `${value}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-300 bg-white p-6">
          <h2 className="text-lg font-semibold">Add These Keywords</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {scoreResult.keyword_gaps.length === 0 ? <li>No critical gaps found.</li> : null}
            {scoreResult.keyword_gaps.map((item) => (
              <li key={item} className="rounded-lg bg-slate-100 px-3 py-2">
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-slate-300 bg-white p-6">
          <h2 className="text-lg font-semibold">Weak Sections</h2>
          <ul className="mt-3 space-y-3 text-sm text-slate-700">
            {Object.entries(scoreResult.weak_sections).length === 0 ? <li>All sections look healthy.</li> : null}
            {Object.entries(scoreResult.weak_sections).map(([section, suggestion]) => (
              <li key={section}>
                <span className="font-semibold capitalize">{section}: </span>
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {error ? <p className="mt-5 text-sm text-red-600">{error}</p> : null}

      <button
        onClick={handleOptimize}
        disabled={loading}
        className="mt-8 rounded-xl bg-emerald-700 px-8 py-3 text-base font-semibold text-white disabled:opacity-60"
      >
        {loading ? "Optimizing..." : "Build ATS-optimized resume"}
      </button>

      {optimizeJobId ? <p className="mt-3 text-xs text-slate-500">Optimize job: {optimizeJobId}</p> : null}
    </main>
  );
}
