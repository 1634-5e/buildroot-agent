import { useEffect, useState } from 'react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastProps {
  message: string;
  type: ToastType;
  onClose: () => void;
}

const icons = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
};

const typeStyles = {
  success: 'border-l-4 border-accent-success',
  error: 'border-l-4 border-accent-error',
  warning: 'border-l-4 border-accent-warning',
  info: 'border-l-4 border-accent-primary',
};

export function Toast({ message, type, onClose }: ToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onClose, 300);
    }, 3000);

    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div
      className={`${typeStyles[type]} transition-all duration-300 ${
        visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-full'
      } bg-bg-secondary border border-border rounded-md shadow-lg flex items-center gap-3 p-4 min-w-[300px]`}
    >
      <span className="text-xl">{icons[type]}</span>
      <span className="text-text-primary">{message}</span>
    </div>
  );
}

export function ToastContainer({ toasts, removeToast }: {
  toasts: Array<{ id: string; message: string; type: ToastType }>;
  removeToast: (id: string) => void;
}) {
  return (
    <div className="fixed top-6 right-6 z-50 flex flex-col gap-3">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
}
