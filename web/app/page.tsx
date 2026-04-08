"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { analyzeResume, getAtsRoles } from "../lib/api";
import { useAtsSessionStore } from "../store/atsSession";

export default function LandingPage() {
  const router = useRouter();
  const {
    resumeFile,
    jdMode,
    jdText,
    roleId,
    roles,
    setResumeFile,
    setJdMode,
    setJdText,
    setRoleId,
    setRoles,
    setScoreResult,
    setOptimizedResume,
    setOptimizeJobId,
    getAnalyzeInput,
  } = useAtsSessionStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getAtsRoles()
      .then((payload) => setRoles(payload))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load roles"));
  }, [setRoles]);

  const roleCards = useMemo(() => Object.entries(roles), [roles]);

  const isSubmitDisabled = !resumeFile || (jdMode === "paste" ? jdText.trim().length < 20 : !roleId);

  async function onSubmit() {
    if (!resumeFile) {
      return;
    }
    setError("");
    setLoading(true);
    setOptimizedResume(null);
    setOptimizeJobId("");

    try {
      const result = await analyzeResume(resumeFile, getAnalyzeInput());
      setScoreResult(result);
      router.push("/results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyze request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-6 py-10 text-slate-900">
      <h1 className="text-4xl font-bold tracking-tight">ATS Resume Optimizer</h1>
      <p className="mt-2 text-slate-600">One flow: score, optimize, and download.</p>

      <section className="mt-8 rounded-2xl border border-slate-300 bg-white/80 p-6 shadow-sm">
        <h2 className="text-xl font-semibold">1. Upload Resume</h2>
        <p className="mt-1 text-sm text-slate-500">Accepted formats: PDF, DOCX</p>
        <label className="mt-4 block rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6">
          <input
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="block w-full text-sm"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              if (!file) {
                setResumeFile(null);
                return;
              }
              const ok = file.name.toLowerCase().endsWith(".pdf") || file.name.toLowerCase().endsWith(".docx");
              if (!ok) {
                setError("Only PDF or DOCX is allowed.");
                setResumeFile(null);
                return;
              }
              setResumeFile(file);
            }}
          />
          {resumeFile ? <p className="mt-3 text-sm text-emerald-700">Selected: {resumeFile.name}</p> : null}
        </label>
      </section>

      <section className="mt-6 rounded-2xl border border-slate-300 bg-white/80 p-6 shadow-sm">
        <h2 className="text-xl font-semibold">2. Job Target</h2>
        <div className="mt-4 flex gap-2">
          <button
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${jdMode === "paste" ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-700"}`}
            onClick={() => setJdMode("paste")}
          >
            Paste job description
          </button>
          <button
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${jdMode === "role" ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-700"}`}
            onClick={() => setJdMode("role")}
          >
            Select job category
          </button>
        </div>

        {jdMode === "paste" ? (
          <textarea
            value={jdText}
            onChange={(event) => setJdText(event.target.value)}
            placeholder="Paste JD here..."
            className="mt-4 h-44 w-full rounded-xl border border-slate-300 bg-white p-3"
          />
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {roleCards.map(([id, spec]) => (
              <button
                key={id}
                onClick={() => setRoleId(id)}
                className={`rounded-xl border p-3 text-left transition ${
                  roleId === id ? "border-emerald-600 bg-emerald-50" : "border-slate-300 bg-white hover:border-slate-500"
                }`}
              >
                <p className="text-sm font-semibold">{spec.display_name}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">{spec.category}</p>
              </button>
            ))}
          </div>
        )}
      </section>

      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      <button
        onClick={onSubmit}
        disabled={isSubmitDisabled || loading}
        className="mt-8 rounded-xl bg-emerald-700 px-6 py-3 text-base font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Scoring..." : "Check ATS Score"}
      </button>
    </main>
  );
}
