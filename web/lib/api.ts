export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type ResumeTemplateKey = "classic" | "compact" | "modern";

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    created_at: string;
  };
}

export interface ParseUploadResponse {
  prefill: Record<string, string>;
  resume_input: ResumeInputPayload;
  extracted_text_preview: string;
}

export interface ResumeInputPayload {
  personal_info: {
    full_name: string;
    email: string;
    phone: string;
    linkedin: string;
    github: string;
    portfolio: string;
    location: string;
  };
  career_summary: string;
  target_role: string;
  target_company: string;
  job_description: string;
  tone: string;
  skills: string[];
  education: Array<{
    degree: string;
    institution: string;
    duration: string;
    location: string;
    details: string;
  }>;
  experiences: Array<{
    role: string;
    company: string;
    duration: string;
    location: string;
    bullet_points: string[];
  }>;
  projects: Array<{
    name: string;
    technologies: string;
    year: string;
    bullet_points: string[];
  }>;
  certifications: string[];
  achievements: string[];
}

export interface ResumeJobQueuedResponse {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  queue_backend: string;
}

export interface ResumeJobStatusResponse {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  template_key: ResumeTemplateKey;
  created_at: string;
  updated_at: string;
  error_message: string;
  result_payload: Record<string, unknown>;
  record_id: string | null;
  pdf_download_url: string;
}

function resolveApiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }

  const normalizedPath = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
  if (normalizedPath.startsWith("/api/")) {
    const apiOrigin = API_BASE_URL.replace(/\/api\/v1$/, "");
    return `${apiOrigin}${normalizedPath}`;
  }

  return `${API_BASE_URL}${normalizedPath}`;
}

function formatApiErrorDetail(detail: unknown): string | null {
  if (!detail) {
    return null;
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        if (item && typeof item === "object") {
          const maybeItem = item as { msg?: unknown; loc?: unknown };
          const message = typeof maybeItem.msg === "string" ? maybeItem.msg : "";
          const location = Array.isArray(maybeItem.loc)
            ? maybeItem.loc
                .map((part) => (typeof part === "string" || typeof part === "number" ? String(part) : ""))
                .filter(Boolean)
                .join(".")
            : "";

          if (message && location) {
            return `${location}: ${message}`;
          }

          return message;
        }

        return "";
      })
      .filter(Boolean);

    return messages.length > 0 ? messages.join("; ") : null;
  }

  if (typeof detail === "object") {
    const maybeDetail = detail as { message?: unknown; detail?: unknown };
    if (typeof maybeDetail.message === "string") {
      return maybeDetail.message;
    }
    if (typeof maybeDetail.detail === "string") {
      return maybeDetail.detail;
    }
  }

  return null;
}

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const fallback = `API request failed: ${response.status}`;
    let message = fallback;

    try {
      const payload = await response.json();
      message =
        formatApiErrorDetail((payload as { detail?: unknown }).detail) ??
        formatApiErrorDetail(payload) ??
        fallback;
    } catch {
      message = fallback;
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

function getFilenameFromDisposition(disposition: string | null): string {
  if (!disposition) {
    return "resume.pdf";
  }

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const fallbackMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (fallbackMatch?.[1]) {
    return fallbackMatch[1];
  }

  return "resume.pdf";
}

export async function downloadResumePdf(
  pdfDownloadPath: string,
  token: string
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(resolveApiUrl(pdfDownloadPath), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const fallback = `API request failed: ${response.status}`;
    let message = fallback;

    try {
      const payload = await response.json();
      message =
        formatApiErrorDetail((payload as { detail?: unknown }).detail) ??
        formatApiErrorDetail(payload) ??
        fallback;
    } catch {
      message = fallback;
    }

    throw new Error(message);
  }

  const blob = await response.blob();
  const filename = getFilenameFromDisposition(response.headers.get("Content-Disposition"));
  return { blob, filename };
}

export function register(email: string, password: string) {
  return apiRequest<AuthTokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string) {
  return apiRequest<AuthTokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe(token: string) {
  return apiRequest<{ id: string; email: string; created_at: string }>("/auth/me", {}, token);
}

export function parseUpload(file: File, token: string) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<ParseUploadResponse>(
    "/resumes/parse-upload",
    {
      method: "POST",
      body: formData,
      headers: {},
    },
    token
  );
}

export function createResumeJob(
  payload: {
    resume_input: ResumeInputPayload;
    template_key: ResumeTemplateKey;
  },
  token: string
) {
  return apiRequest<ResumeJobQueuedResponse>(
    "/resumes/jobs",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

export function getResumeJob(jobId: string, token: string) {
  return apiRequest<ResumeJobStatusResponse>(`/resumes/jobs/${jobId}`, {}, token);
}

export function listResumeRecords(token: string) {
  return apiRequest<Array<{ id: string; title: string; created_at: string }>>("/resumes/records", {}, token);
}
