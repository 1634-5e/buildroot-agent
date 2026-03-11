// buildroot-web/src/mocks/node.js
// MSW Node 配置（用于测试）

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);