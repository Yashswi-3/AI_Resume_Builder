"use client";

import { useSyncExternalStore } from "react";

import type {
  ATSAnalyzeResponse,
  ATSOptimizedResumePayload,
  ATSRoleMap,
  ATSRoleOrJDInput,
} from "../lib/api";

type JDMode = "paste" | "role";

type AtsSessionData = {
  resumeFile: File | null;
  jdMode: JDMode;
  jdText: string;
  roleId: string;
  roles: ATSRoleMap;
  scoreResult: ATSAnalyzeResponse | null;
  optimizedResume: ATSOptimizedResumePayload | null;
  optimizeJobId: string;
};

type AtsSessionActions = {
  setResumeFile: (file: File | null) => void;
  setJdMode: (mode: JDMode) => void;
  setJdText: (text: string) => void;
  setRoleId: (roleId: string) => void;
  setRoles: (roles: ATSRoleMap) => void;
  setScoreResult: (result: ATSAnalyzeResponse | null) => void;
  setOptimizedResume: (result: ATSOptimizedResumePayload | null) => void;
  setOptimizeJobId: (jobId: string) => void;
  getAnalyzeInput: () => ATSRoleOrJDInput;
  reset: () => void;
};

type AtsSessionStore = AtsSessionData & AtsSessionActions;

const listeners = new Set<() => void>();

const initialData: AtsSessionData = {
  resumeFile: null,
  jdMode: "paste",
  jdText: "",
  roleId: "",
  roles: {},
  scoreResult: null,
  optimizedResume: null,
  optimizeJobId: "",
};

let data: AtsSessionData = { ...initialData };

function emit() {
  listeners.forEach((listener) => listener());
}

function patch(next: Partial<AtsSessionData>) {
  data = { ...data, ...next };
  snapshot = {
    ...data,
    ...actions,
  };
  emit();
}

const actions: AtsSessionActions = {
  setResumeFile: (file) => patch({ resumeFile: file }),
  setJdMode: (mode) => patch({ jdMode: mode }),
  setJdText: (text) => patch({ jdText: text }),
  setRoleId: (roleId) => patch({ roleId }),
  setRoles: (roles) => patch({ roles }),
  setScoreResult: (result) => patch({ scoreResult: result }),
  setOptimizedResume: (result) => patch({ optimizedResume: result }),
  setOptimizeJobId: (jobId) => patch({ optimizeJobId: jobId }),
  getAnalyzeInput: () => {
    if (data.jdMode === "role") {
      return { role_id: data.roleId, jd_text: "" };
    }
    return { role_id: "", jd_text: data.jdText };
  },
  reset: () => {
    patch({ ...initialData });
  },
};

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): AtsSessionStore {
  return snapshot;
}

let snapshot: AtsSessionStore = {
  ...data,
  ...actions,
};

export function useAtsSessionStore(): AtsSessionStore {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
