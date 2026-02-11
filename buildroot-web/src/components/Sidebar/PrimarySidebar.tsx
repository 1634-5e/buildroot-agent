import { Settings } from 'lucide-react';

interface PrimarySidebarProps {
  currentView: 'devices';
  onViewChange: (view: 'devices') => void;
  onSettingsClick: () => void;
}

export function PrimarySidebar({ currentView, onViewChange, onSettingsClick }: PrimarySidebarProps) {
  return (
    <nav className="w-16 bg-bg-secondary border-r border-border flex flex-col items-center py-4 gap-2">
      <div className="w-10 h-10 bg-gradient-to-br from-accent-primary to-accent-secondary rounded-lg flex items-center justify-center text-xl mb-4 shadow-lg">
        🖥️
      </div>

      <button
        onClick={() => onViewChange('devices')}
        className={`w-12 h-12 rounded-lg flex items-center justify-center text-xl transition-all relative ${
          currentView === 'devices'
            ? 'bg-accent-primary/15 text-accent-primary'
            : 'text-text-secondary hover:bg-bg-tertiary'
        }`}
      >
        📱
        {currentView === 'devices' && (
          <span className="absolute -left-4 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-accent-primary rounded-r" />
        )}
      </button>

      <button
        onClick={onSettingsClick}
        className="w-12 h-12 rounded-lg flex items-center justify-center text-text-secondary hover:bg-bg-tertiary transition-all text-xl"
      >
        <Settings size={24} />
      </button>
    </nav>
  );
}
