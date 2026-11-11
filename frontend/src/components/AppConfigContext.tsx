/**
 * Application configuration, loaded once from GET /api/config.
 *
 * This is what makes the "Demo AI Mode" labelling honest: the flag comes from
 * the backend that actually produced the output, not from a frontend constant.
 */

import { createContext, useContext, type ReactNode } from 'react';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import type { AppConfig } from '../types/api';

interface ConfigState {
  config: AppConfig | null;
  loading: boolean;
  error: string | null;
}

const ConfigContext = createContext<ConfigState>({
  config: null,
  loading: true,
  error: null,
});

export function AppConfigProvider({ children }: { children: ReactNode }) {
  const { data, loading, error } = useApi(() => api.config(), []);
  return (
    <ConfigContext.Provider value={{ config: data, loading, error }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useAppConfig(): ConfigState {
  return useContext(ConfigContext);
}

/** Convenience: true only when the backend confirms it is running mock AI. */
export function useDemoMode(): boolean {
  return useAppConfig().config?.ai.demo_mode ?? false;
}
