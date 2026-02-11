/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEFAULT_WS_URL?: string;
  readonly VITE_DEFAULT_MAX_RECONNECT?: string;
  readonly VITE_DEFAULT_REFRESH_INTERVAL?: string;
  readonly VITE_DEFAULT_AUTO_SELECT?: string;
  readonly VITE_APP_TITLE?: string;
  readonly VITE_APP_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
