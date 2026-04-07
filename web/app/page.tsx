"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import {
  API_BASE_URL,
  ResumeInputPayload,
  ResumeJobStatusResponse,
  ResumeTemplateKey,
  createResumeJob,
  downloadResumePdf,
  getMe,
  getResumeJob,
  listResumeRecords,
  login,
  parseUpload,
  register,
} from "../lib/api";

type FormState = {
  full_name: string;
  email: string;
  phone: string;
  linkedin: string;
  github: string;
  portfolio: string;
  location: string;
  career_summary: string;
  target_role: string;
  target_company: string;
  tone: string;
  job_description: string;
  skills_raw: string;
  education_raw: string;
  experience_raw: string;
  projects_raw: string;
  certifications_raw: string;
  achievements_raw: string;
};

const EMPTY_FORM: FormState = {
  full_name: "",
  email: "",
  phone: "",
  linkedin: "",
  github: "",
  portfolio: "",
  location: "",
  career_summary: "",
  target_role: "Software Engineer",
  target_company: "",
  tone: "professional",
  job_description: "",
  skills_raw: "",
  education_raw: "",
  experience_raw: "",
  projects_raw: "",
  certifications_raw: "",
  achievements_raw: "",
};

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitBlocks(value: string): string[] {
  return value
    .split(/\n\s*\n/g)
    .map((block) => block.trim())
    .filter(Boolean);
}

function parseSkills(raw: string): string[] {
  return raw
    .split(/[\n,]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function parseEducation(raw: string): ResumeInputPayload["education"] {
  return splitLines(raw).map((line) => {
    const parts = line.split("|").map((item) => item.trim());
    return {
      degree: parts[0] ?? "",
      institution: parts[1] ?? "",
      duration: parts[2] ?? "",
      location: parts[3] ?? "",
      details: parts.slice(4).join(" | ").trim(),
    };
  });
}

function parseExperience(raw: string): ResumeInputPayload["experiences"] {
  return splitBlocks(raw).map((block) => {
    const lines = splitLines(block);
    const header = (lines[0] ?? "").split("|").map((item) => item.trim());
    const bullets = lines
      .slice(1)
      .map((line) => line.replace(/^[-*•]\s*/, "").trim())
      .filter(Boolean);

    return {
      role: header[0] ?? "",
      company: header[1] ?? "",
      duration: header[2] ?? "",
      location: header[3] ?? "",
      bullet_points: bullets,
    };
  });
}

function parseProjects(raw: string): ResumeInputPayload["projects"] {
  return splitBlocks(raw).map((block) => {
    const lines = splitLines(block);
    const header = (lines[0] ?? "").split("|").map((item) => item.trim());
    const bullets = lines
      .slice(1)
      .map((line) => line.replace(/^[-*•]\s*/, "").trim())
      .filter(Boolean);

    return {
      name: header[0] ?? "",
      technologies: header[1] ?? "",
      year: header[2] ?? "",
      bullet_points: bullets,
    };
  });
}

function parseSimpleList(raw: string): string[] {
  return splitLines(raw);
}

function toResumeInputPayload(form: FormState): ResumeInputPayload {
  return {
    personal_info: {
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      linkedin: form.linkedin.trim(),
      github: form.github.trim(),
      portfolio: form.portfolio.trim(),
      location: form.location.trim(),
    },
    career_summary: form.career_summary.trim(),
    target_role: form.target_role.trim(),
    target_company: form.target_company.trim(),
    job_description: form.job_description.trim(),
    tone: form.tone.trim() || "professional",
    skills: parseSkills(form.skills_raw),
    education: parseEducation(form.education_raw),
    experiences: parseExperience(form.experience_raw),
    projects: parseProjects(form.projects_raw),
    certifications: parseSimpleList(form.certifications_raw),
    achievements: parseSimpleList(form.achievements_raw),
  };
}

function payloadToForm(payload: ResumeInputPayload): FormState {
  const educationRaw = payload.education
    .map((item) => [item.degree, item.institution, item.duration, item.location, item.details].join(" | "))
    .join("\n");

  const experienceRaw = payload.experiences
    .map((item) => {
      const header = [item.role, item.company, item.duration, item.location].join(" | ");
      const bullets = item.bullet_points.map((point) => `- ${point}`);
      return [header, ...bullets].join("\n");
    })
    .join("\n\n");

  const projectsRaw = payload.projects
    .map((item) => {
      const header = [item.name, item.technologies, item.year].join(" | ");
      const bullets = item.bullet_points.map((point) => `- ${point}`);
      return [header, ...bullets].join("\n");
    })
    .join("\n\n");

  return {
    full_name: payload.personal_info.full_name,
    email: payload.personal_info.email,
    phone: payload.personal_info.phone,
    linkedin: payload.personal_info.linkedin,
    github: payload.personal_info.github,
    portfolio: payload.personal_info.portfolio,
    location: payload.personal_info.location,
    career_summary: payload.career_summary,
    target_role: payload.target_role,
    target_company: payload.target_company,
    tone: payload.tone,
    job_description: payload.job_description,
    skills_raw: payload.skills.join(", "),
    education_raw: educationRaw,
    experience_raw: experienceRaw,
    projects_raw: projectsRaw,
    certifications_raw: payload.certifications.join("\n"),
    achievements_raw: payload.achievements.join("\n"),
  };
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3 mt-8">
      <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>
      {subtitle ? <p className="mt-1 text-sm text-slate-600">{subtitle}</p> : null}
    </div>
  );
}

export default function HomePage() {
  const [token, setToken] = useState<string>("");
  const [viewerEmail, setViewerEmail] = useState<string>("");
  const [authEmail, setAuthEmail] = useState<string>("");
  const [authPassword, setAuthPassword] = useState<string>("");
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [templateKey, setTemplateKey] = useState<ResumeTemplateKey>("classic");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [parseLoading, setParseLoading] = useState(false);

  const [activeJobId, setActiveJobId] = useState<string>("");
  const [jobStatus, setJobStatus] = useState<ResumeJobStatusResponse | null>(null);
  const [generateLoading, setGenerateLoading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [records, setRecords] = useState<Array<{ id: string; title: string; created_at: string }>>([]);
  const [recordsLoading, setRecordsLoading] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string>("");
  const [noticeMessage, setNoticeMessage] = useState<string>("");

  useEffect(() => {
    const savedToken = window.localStorage.getItem("resume_builder_token");
    if (!savedToken) {
      return;
    }

    setToken(savedToken);
    getMe(savedToken)
      .then((user) => {
        setViewerEmail(user.email);
        setForm((prev) => ({ ...prev, email: prev.email || user.email }));
      })
      .catch(() => {
        window.localStorage.removeItem("resume_builder_token");
        setToken("");
      });
  }, []);

  useEffect(() => {
    if (!activeJobId || !token) {
      return;
    }

    let isCancelled = false;

    const timer = window.setInterval(async () => {
      try {
        const status = await getResumeJob(activeJobId, token);
        if (isCancelled) {
          return;
        }

        setJobStatus(status);
        if (status.status === "completed" || status.status === "failed") {
          setGenerateLoading(false);
          setActiveJobId("");
          if (status.status === "completed") {
            setNoticeMessage("Resume generation completed.");
            void refreshRecords(token);
          }
          if (status.status === "failed") {
            setErrorMessage(status.error_message || "Generation failed.");
          }
        }
      } catch (error) {
        if (!isCancelled) {
          setGenerateLoading(false);
          setActiveJobId("");
          setErrorMessage(error instanceof Error ? error.message : "Failed to poll job status.");
        }
      }
    }, 2000);

    return () => {
      isCancelled = true;
      window.clearInterval(timer);
    };
  }, [activeJobId, token]);

  const markdownPreview = useMemo(() => {
    const markdown = jobStatus?.result_payload?.markdown;
    return typeof markdown === "string" ? markdown : "";
  }, [jobStatus]);

  async function refreshRecords(authToken: string) {
    setRecordsLoading(true);
    try {
      const latest = await listResumeRecords(authToken);
      setRecords(latest);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not load resume records.");
    } finally {
      setRecordsLoading(false);
    }
  }

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setNoticeMessage("");

    if (authPassword.length < 8) {
      setErrorMessage("Password must be at least 8 characters.");
      return;
    }

    setAuthLoading(true);

    try {
      const response = isRegisterMode
        ? await register(authEmail.trim(), authPassword)
        : await login(authEmail.trim(), authPassword);

      setToken(response.access_token);
      setViewerEmail(response.user.email);
      setForm((prev) => ({ ...prev, email: prev.email || response.user.email }));
      window.localStorage.setItem("resume_builder_token", response.access_token);
      setNoticeMessage(isRegisterMode ? "Account created." : "Signed in successfully.");
      await refreshRecords(response.access_token);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleParseUpload() {
    if (!token) {
      setErrorMessage("Sign in before parsing uploads.");
      return;
    }
    if (!uploadFile) {
      setErrorMessage("Choose a PDF or DOCX file first.");
      return;
    }

    setParseLoading(true);
    setErrorMessage("");
    setNoticeMessage("");

    try {
      const parsed = await parseUpload(uploadFile, token);
      setForm(payloadToForm(parsed.resume_input));
      setNoticeMessage("Resume parsed and mapped into the form. Review before generating.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Upload parse failed.");
    } finally {
      setParseLoading(false);
    }
  }

  async function handleGenerate() {
    if (!token) {
      setErrorMessage("Sign in before generating resumes.");
      return;
    }

    setGenerateLoading(true);
    setErrorMessage("");
    setNoticeMessage("");
    setJobStatus(null);

    try {
      const payload = {
        resume_input: toResumeInputPayload(form),
        template_key: templateKey,
      };
      const queued = await createResumeJob(payload, token);
      setActiveJobId(queued.job_id);
      setNoticeMessage(`Job queued via ${queued.queue_backend}. Polling status...`);
    } catch (error) {
      setGenerateLoading(false);
      setErrorMessage(error instanceof Error ? error.message : "Generation request failed.");
    }
  }

  async function handleDownloadPdf() {
    if (!token) {
      setErrorMessage("Sign in before downloading PDFs.");
      return;
    }

    if (!jobStatus?.pdf_download_url) {
      setErrorMessage("No downloadable PDF is available for this job.");
      return;
    }

    setDownloadLoading(true);
    setErrorMessage("");

    try {
      const { blob, filename } = await downloadResumePdf(jobStatus.pdf_download_url, token);
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename || "resume.pdf";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(objectUrl);
      setNoticeMessage("PDF download started.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to download PDF.");
    } finally {
      setDownloadLoading(false);
    }
  }

  function handleLogout() {
    setToken("");
    setViewerEmail("");
    setRecords([]);
    window.localStorage.removeItem("resume_builder_token");
    setNoticeMessage("Signed out.");
  }

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <main className="mx-auto max-w-6xl px-4 pb-20 pt-10 md:px-8">
      <div className="mb-8 rounded-3xl border border-emerald-900/10 bg-white/85 p-7 shadow-soft backdrop-blur-sm">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-900/70">Live Product Console</p>
            <h1 className="mt-2 text-4xl font-bold tracking-tight text-ink">AI Resume Builder</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">
              Production flow: authenticated user to upload parse to validated form to queued AI generation to async status to PDF download.
            </p>
          </div>
          <div className="rounded-2xl bg-emerald-900 px-4 py-3 text-white">
            <p className="text-xs uppercase tracking-wider text-emerald-100">Environment</p>
            <p className="text-sm font-semibold">API: {API_BASE_URL}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <section className="rounded-3xl border border-emerald-900/10 bg-white/90 p-6 shadow-soft lg:col-span-2">
          <SectionTitle
            title="Auth"
            subtitle="Register or login to persist resumes, queue jobs, and download generated PDFs."
          />

          <form className="space-y-3" onSubmit={handleAuthSubmit}>
            <input
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Email"
              type="email"
              value={authEmail}
              onChange={(event) => setAuthEmail(event.target.value)}
              required
            />
            <input
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Password"
              type="password"
              value={authPassword}
              onChange={(event) => setAuthPassword(event.target.value)}
              minLength={8}
              title="Password must be at least 8 characters."
              required
            />
            <button
              className="w-full rounded-xl bg-forest px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              type="submit"
              disabled={authLoading}
            >
              {authLoading ? "Please wait..." : isRegisterMode ? "Create Account" : "Sign In"}
            </button>
          </form>

          <div className="mt-3 flex items-center justify-between text-xs text-slate-600">
            <button
              className="rounded px-2 py-1 hover:bg-slate-100"
              onClick={() => setIsRegisterMode((prev) => !prev)}
              type="button"
            >
              {isRegisterMode ? "Have an account? Sign in" : "New here? Create account"}
            </button>
            {token ? (
              <button className="rounded px-2 py-1 hover:bg-slate-100" onClick={handleLogout} type="button">
                Logout ({viewerEmail})
              </button>
            ) : null}
          </div>

          <SectionTitle title="Upload" subtitle="Parse a PDF/DOCX and auto-fill the form." />
          <input
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            type="file"
            accept=".pdf,.docx"
            onChange={(event: ChangeEvent<HTMLInputElement>) => setUploadFile(event.target.files?.[0] ?? null)}
          />
          <button
            className="mt-3 w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleParseUpload}
            type="button"
            disabled={parseLoading || !uploadFile}
          >
            {parseLoading ? "Parsing..." : "Parse Upload"}
          </button>

          <SectionTitle title="Template" subtitle="Switch output structure per target usage." />
          <select
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            value={templateKey}
            onChange={(event) => setTemplateKey(event.target.value as ResumeTemplateKey)}
          >
            <option value="classic">Classic ATS</option>
            <option value="compact">Compact Recruiter</option>
            <option value="modern">Modern Portfolio</option>
          </select>

          <button
            className="mt-4 w-full rounded-xl bg-ink px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleGenerate}
            type="button"
            disabled={generateLoading}
          >
            {generateLoading ? "Generating via queue..." : "Generate Resume"}
          </button>

          {jobStatus ? (
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
              <p>
                <span className="font-semibold">Job:</span> {jobStatus.job_id}
              </p>
              <p>
                <span className="font-semibold">Status:</span> {jobStatus.status}
              </p>
              <p>
                <span className="font-semibold">Template:</span> {jobStatus.template_key}
              </p>
            </div>
          ) : null}

          {recordsLoading ? <p className="mt-4 text-xs text-slate-600">Loading records...</p> : null}
          {records.length > 0 ? (
            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Recent Records</p>
              <ul className="space-y-2 text-xs text-slate-700">
                {records.slice(0, 6).map((record) => (
                  <li key={record.id} className="flex items-center justify-between gap-2">
                    <span className="truncate">{record.title}</span>
                    <span className="text-slate-500">{new Date(record.created_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="rounded-3xl border border-emerald-900/10 bg-white/90 p-6 shadow-soft lg:col-span-3">
          <SectionTitle title="Resume Input" subtitle="Structured fields are validated before queueing generation." />

          <div className="grid gap-3 md:grid-cols-2">
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Full Name"
              value={form.full_name}
              onChange={(event) => updateField("full_name", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Email"
              value={form.email}
              onChange={(event) => updateField("email", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Phone"
              value={form.phone}
              onChange={(event) => updateField("phone", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Location"
              value={form.location}
              onChange={(event) => updateField("location", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="LinkedIn URL"
              value={form.linkedin}
              onChange={(event) => updateField("linkedin", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="GitHub URL"
              value={form.github}
              onChange={(event) => updateField("github", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm md:col-span-2"
              placeholder="Portfolio URL"
              value={form.portfolio}
              onChange={(event) => updateField("portfolio", event.target.value)}
            />
          </div>

          <SectionTitle title="Professional Settings" />
          <div className="grid gap-3 md:grid-cols-3">
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Target Role"
              value={form.target_role}
              onChange={(event) => updateField("target_role", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Target Company"
              value={form.target_company}
              onChange={(event) => updateField("target_company", event.target.value)}
            />
            <input
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
              placeholder="Tone"
              value={form.tone}
              onChange={(event) => updateField("tone", event.target.value)}
            />
          </div>

          <textarea
            className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Career summary"
            value={form.career_summary}
            onChange={(event) => updateField("career_summary", event.target.value)}
          />

          <textarea
            className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Target job description"
            value={form.job_description}
            onChange={(event) => updateField("job_description", event.target.value)}
          />

          <SectionTitle title="Core Sections" subtitle="Use heading formats: Education line, Experience block, Project block." />
          <textarea
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Skills (comma or new line separated)"
            value={form.skills_raw}
            onChange={(event) => updateField("skills_raw", event.target.value)}
          />
          <textarea
            className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Education (Degree | Institution | Duration | Location | Details)"
            value={form.education_raw}
            onChange={(event) => updateField("education_raw", event.target.value)}
          />
          <textarea
            className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Experience blocks (Role | Company | Duration | Location then bullet lines)"
            value={form.experience_raw}
            onChange={(event) => updateField("experience_raw", event.target.value)}
          />
          <textarea
            className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Projects blocks (Name | Technologies | Year then bullet lines)"
            value={form.projects_raw}
            onChange={(event) => updateField("projects_raw", event.target.value)}
          />
          <textarea
            className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Certifications (one per line)"
            value={form.certifications_raw}
            onChange={(event) => updateField("certifications_raw", event.target.value)}
          />
          <textarea
            className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="Achievements (one per line)"
            value={form.achievements_raw}
            onChange={(event) => updateField("achievements_raw", event.target.value)}
          />
        </section>
      </div>

      {noticeMessage ? <p className="mt-6 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{noticeMessage}</p> : null}
      {errorMessage ? <p className="mt-3 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-800">{errorMessage}</p> : null}

      <section className="mt-8 rounded-3xl border border-emerald-900/10 bg-white/90 p-6 shadow-soft">
        <SectionTitle title="Generated Preview" subtitle="Asynchronous result payload with diagnostics and downloadable PDF." />

        {jobStatus?.result_payload ? (
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Markdown</h3>
              <div className="preview-markdown max-h-[500px] overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                {markdownPreview || "No markdown available."}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Diagnostics</h3>
                <pre className="max-h-[220px] overflow-y-auto text-xs text-slate-700">
                  {JSON.stringify(jobStatus.result_payload.diagnostics ?? {}, null, 2)}
                </pre>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Optimization</h3>
                <pre className="max-h-[180px] overflow-y-auto text-xs text-slate-700">
                  {JSON.stringify(
                    {
                      ats_result: jobStatus.result_payload.ats_result ?? {},
                      jd_result: jobStatus.result_payload.jd_result ?? {},
                    },
                    null,
                    2
                  )}
                </pre>
              </div>

              {jobStatus.pdf_download_url ? (
                <button
                  className="inline-flex rounded-xl bg-forest px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={handleDownloadPdf}
                  type="button"
                  disabled={downloadLoading}
                >
                  {downloadLoading ? "Downloading..." : "Download PDF"}
                </button>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-600">No completed generation yet. Submit a job to populate preview and diagnostics.</p>
        )}
      </section>
    </main>
  );
}
