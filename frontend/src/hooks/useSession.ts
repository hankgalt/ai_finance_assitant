import { useQuery } from "@tanstack/react-query";

import { api, ClientApiError } from "../lib/api";

const storageKey = "aifa.local-session-id";

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      const existing = localStorage.getItem(storageKey);
      if (existing) {
        try {
          return await api.getSession(existing);
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
}
