import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { PrincipalView } from "../types/contracts";
import { api, ClientApiError } from "../lib/api";

const legacyLoopbackStorageKey = "aifa.local-session-id";

export function sessionStorageKey(principalId: string): string {
  return `aifa.session.${principalId}`;
}

function storedSessionId(identity: PrincipalView): string | null {
  const storageKey = sessionStorageKey(identity.principal_id);
  const existing = localStorage.getItem(storageKey);
  if (existing || identity.identity_mode !== "loopback_development")
    return existing;
  const legacy = localStorage.getItem(legacyLoopbackStorageKey);
  if (legacy) {
    localStorage.setItem(storageKey, legacy);
    localStorage.removeItem(legacyLoopbackStorageKey);
  }
  return legacy;
}

export function useSession() {
  const queryClient = useQueryClient();
  const [generation, setGeneration] = useState(0);
  const [identity, setIdentity] = useState<PrincipalView | null>(null);
  const session = useQuery({
    queryKey: ["session", generation],
    queryFn: async () => {
      const resolvedIdentity = await api.identity();
      setIdentity(resolvedIdentity);
      const storageKey = sessionStorageKey(resolvedIdentity.principal_id);
      const existing = storedSessionId(resolvedIdentity);
      if (existing) {
        try {
          const restored = await api.getSession(existing);
          if (restored.state === "active") return restored;
          localStorage.removeItem(storageKey);
        } catch (error) {
          if (!(error instanceof ClientApiError) || error.status !== 404)
            throw error;
          localStorage.removeItem(storageKey);
        }
      }
      const created = await api.createSession();
      localStorage.setItem(storageKey, created.session_id);
      return created;
    },
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
  const archiveSession = useMutation({
    mutationFn: async () => {
      const sessionId = session.data?.session_id;
      if (!sessionId) {
        throw new ClientApiError(
          "No active Session is available to archive.",
          null,
          "SESSION_UNAVAILABLE",
        );
      }
      await api.archiveSession(sessionId);
      await queryClient.cancelQueries({
        predicate: (query) => query.queryKey.includes(sessionId),
      });
      queryClient.removeQueries({
        predicate: (query) => query.queryKey.includes(sessionId),
      });
      await queryClient.cancelQueries({ queryKey: ["session"] });
      queryClient.removeQueries({ queryKey: ["session"] });
      if (identity)
        localStorage.removeItem(sessionStorageKey(identity.principal_id));
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["archived-sessions"] });
      setGeneration((current) => current + 1);
    },
  });

  return {
    ...session,
    identity,
    archiveActiveSession: () => archiveSession.mutateAsync(),
    archiveError: archiveSession.error,
    isArchiving: archiveSession.isPending,
    resetArchiveSession: archiveSession.reset,
  };
}
