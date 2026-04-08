"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { exportPDF } from "../../lib/api";
import { useAtsSessionStore } from "../../store/atsSession";

type EditableSectionKey = "summary" | "skills" | "experience" | "projects" | "education";

export default function OptimizePage() {
  const router = useRouter();
  const { optimizedResume, setOptimizedResume, optimizeJobId } = useAtsSessionStore();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  const sections = useMemo(() => {
    if (!optimizedResume) {
      return null;
    }
    return {
      summary: optimizedResume.summary,
      skills: optimizedResume.skills,
      experience: optimizedResume.experience,
      projects: optimizedResume.projects,
      education: optimizedResume.education,
    };
  }, [optimizedResume]);

  if (!sections || !optimizedResume) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-slate-700">No optimized resume found yet.</p>
        <button className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-white" onClick={() => router.push("/results")}>
          Back to Results
        </button>
      </main>
    );
  }

  function updateSection(key: EditableSectionKey, value: string) {
    if (!optimizedResume) {
      return;
    }

    setOptimizedResume({
      skills: key === "skills" ? value : optimizedResume.skills,
      experience: key === "experience" ? value : optimizedResume.experience,
      projects: key === "projects" ? value : optimizedResume.projects,
      education: key === "education" ? value : optimizedResume.education,
      summary: key === "summary" ? value : optimizedResume.summary,
    });
  }

  async function onDownload() {
    if (!optimizeJobId) {
      setError("No optimize job id found.");
      return;
    }
    setDownloading(true);
    setError("");
    try {
      const { blob, filename } = await exportPDF(optimizeJobId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-6 py-10">
      <h1 className="text-3xl font-bold">Optimized Resume</h1>
      <p className="mt-2 text-slate-600">Edit any section inline before downloading.</p>

      {(["summary", "skills", "experience", "projects", "education"] as const).map((key) => (
        <section key={key} className="mt-5 rounded-2xl border border-slate-300 bg-white p-5">
          <h2 className="text-lg font-semibold capitalize">{key}</h2>
          <textarea
            className="mt-3 h-36 w-full rounded-lg border border-slate-300 p-3 font-mono text-sm"
            value={sections[key]}
            onChange={(event) => updateSection(key, event.target.value)}
          />
        </section>
      ))}

      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      <button
        onClick={onDownload}
        disabled={downloading}
        className="mt-8 rounded-xl bg-slate-900 px-7 py-3 text-base font-semibold text-white disabled:opacity-60"
      >
        {downloading ? "Preparing PDF..." : "Download PDF"}
      </button>
    </main>
  );
}
