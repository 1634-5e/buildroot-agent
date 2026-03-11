// buildroot-web/src/mocks/handlers.js
// Mock API 处理器

import { http, HttpResponse, ws } from 'msw';

// Mock 设备数据
const mockDevices = [
  {
    id: 'demo-device-1',
    name: 'Demo Device 1',
    status: 'online',
    ip: '192.168.1.100',
    last_seen: new Date().toISOString(),
    system_info: {
      hostname: 'buildroot-demo',
      version: '1.0.0',
      uptime: 3600,
      cpu_usage: 25.5,
      memory_usage: 45.2,
      disk_usage: 60.0
    }
  }
];

// Mock 文件系统
const mockFiles = {
  '/': [
    { name: 'etc', type: 'directory', size: 0 },
    { name: 'tmp', type: 'directory', size: 0 },
    { name: 'var', type: 'directory', size: 0 },
    { name: 'config.txt', type: 'file', size: 1024 }
  ],
  '/etc': [
    { name: 'hosts', type: 'file', size: 256 },
    { name: 'config', type: 'directory', size: 0 }
  ]
};

export const handlers = [
  // 设备列表
  http.get('/api/devices', () => {
    return HttpResponse.json({
      code: 0,
      data: mockDevices,
      message: 'success'
    });
  }),

  // 设备详情
  http.get('/api/devices/:id', ({ params }) => {
    const device = mockDevices.find(d => d.id === params.id);
    return HttpResponse.json({
      code: 0,
      data: device || null,
      message: device ? 'success' : 'device not found'
    });
  }),

  // 系统状态
  http.get('/api/devices/:id/system', ({ params }) => {
    return HttpResponse.json({
      code: 0,
      data: {
        cpu_usage: Math.random() * 100,
        memory_usage: Math.random() * 100,
        disk_usage: Math.random() * 100,
        uptime: 3600 + Math.floor(Math.random() * 1000),
        temperature: 45 + Math.random() * 20
      },
      message: 'success'
    });
  }),

  // 文件列表
  http.get('/api/devices/:id/files', ({ request }) => {
    const url = new URL(request.url);
    const path = url.searchParams.get('path') || '/';
    return HttpResponse.json({
      code: 0,
      data: mockFiles[path] || [],
      message: 'success'
    });
  }),

  // Ping 测试
  http.post('/api/devices/:id/ping', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      code: 0,
      data: {
        target: body.target,
        packets_sent: 4,
        packets_received: 4,
        packet_loss: 0,
        min_time: 0.5,
        max_time: 2.3,
        avg_time: 1.2
      },
      message: 'success'
    });
  }),

  // 执行命令
  http.post('/api/devices/:id/command', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      code: 0,
      data: {
        command: body.command,
        output: `Mock output for: ${body.command}\nTotal: 10\nUsed: 5\nFree: 5`,
        exit_code: 0,
        execution_time: 0.123
      },
      message: 'success'
    });
  }),

  // 登录
  http.post('/api/auth/login', async () => {
    return HttpResponse.json({
      code: 0,
      data: {
        token: 'mock-jwt-token-' + Date.now(),
        user: {
          id: 'admin',
          name: 'Admin',
          role: 'admin'
        }
      },
      message: 'success'
    });
  }),

  // WebSocket (模拟)
  ws.link('wss://*/ws', {
    onConnection({ client }) {
      console.log('Mock WebSocket connected');
      
      // 发送欢迎消息
      client.send(JSON.stringify({
        type: 'connected',
        message: 'Mock WebSocket connected'
      }));

      // 模拟定期心跳
      const interval = setInterval(() => {
        client.send(JSON.stringify({
          type: 'heartbeat',
          timestamp: Date.now()
        }));
      }, 30000);

      client.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);
        
        // 模拟响应
        if (data.type === 'ping') {
          client.send(JSON.stringify({
            type: 'pong',
            timestamp: Date.now()
          }));
        }
      });

      client.addEventListener('close', () => {
        clearInterval(interval);
      });
    }
  })
];

// 模拟延迟
export const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));