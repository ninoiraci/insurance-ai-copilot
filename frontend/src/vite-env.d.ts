/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Overrides the API root. Defaults to /api, served through the Vite proxy. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
