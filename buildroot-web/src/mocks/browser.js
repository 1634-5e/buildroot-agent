// buildroot-web/src/mocks/browser.js
// MSW Browser 配置

import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);

// 启动 Mock
export async function startMockAPI() {
  if (import.meta.env.DEV || import.meta.env.VITE_USE_MOCK === 'true') {
    await worker.start({
      onUnhandledRequest: 'bypass', // 未匹配的请求直接放行
      serviceWorker: {
        url: '/mockServiceWorker.js'
      }
    });
    console.log('[MSW] Mock API started');
  }
}