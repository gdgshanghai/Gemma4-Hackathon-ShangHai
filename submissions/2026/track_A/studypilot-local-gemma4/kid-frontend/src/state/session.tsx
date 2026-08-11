import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { EveningApiError, getTodayEvening } from "../api/client";
import type { EveningResponse } from "../api/contracts";

const TODAY_QUERY_KEY = ["evening", "today"] as const;

type SessionContextValue = {
  session: EveningResponse | undefined;
  isRestoring: boolean;
  restoreError: boolean;
  notice: string | null;
  clearNotice: () => void;
  acceptResponse: (response: EveningResponse) => void;
  handleActionError: (error: unknown) => Promise<void>;
  retryRestore: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const query = useQuery({
    queryKey: TODAY_QUERY_KEY,
    queryFn: getTodayEvening,
    retry: false,
    staleTime: 0,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });

  const acceptResponse = useCallback(
    (response: EveningResponse) => {
      queryClient.setQueryData(TODAY_QUERY_KEY, response);
    },
    [queryClient],
  );

  const handleActionError = useCallback(
    async (error: unknown) => {
      if (error instanceof EveningApiError && error.status === 503) {
        if (error.recovery) acceptResponse(error.recovery);
        setNotice("你的输入已经保存，但本地模型暂时不可用，请稍后重试。");
        return;
      }
      if (error instanceof EveningApiError && error.status === 409) {
        try {
          await queryClient.fetchQuery({
            queryKey: TODAY_QUERY_KEY,
            queryFn: getTodayEvening,
          });
          setNotice("今晚的状态已更新，请按最新页面继续。");
        } catch {
          setNotice("状态发生变化，但暂时无法刷新，请稍后再试。");
        }
        return;
      }
      if (error instanceof EveningApiError && error.status === 422) {
        setNotice("这次输入还不能提交，请检查后再试。");
        return;
      }
      setNotice("暂时无法连接本地服务，请确认服务已启动后重试。");
    },
    [acceptResponse, queryClient],
  );

  const retryRestore = useCallback(async () => {
    await query.refetch();
  }, [query]);

  const clearNotice = useCallback(() => setNotice(null), []);
  const value = useMemo<SessionContextValue>(
    () => ({
      session: query.data ?? undefined,
      isRestoring: query.isPending,
      restoreError: query.isError,
      notice,
      clearNotice,
      acceptResponse,
      handleActionError,
      retryRestore,
    }),
    [
      acceptResponse,
      clearNotice,
      handleActionError,
      notice,
      query.data,
      query.isError,
      query.isPending,
      retryRestore,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
