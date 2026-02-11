import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { App } from './components/App';
import { WebSocketProvider } from './contexts/WebSocketContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <WebSocketProvider>
      <App />
    </WebSocketProvider>
  </React.StrictMode>,
);
