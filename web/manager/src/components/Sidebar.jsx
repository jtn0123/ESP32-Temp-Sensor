import { useState } from 'react';
import {
  LayoutDashboard,
  Monitor,
  Zap,
  Terminal,
  Radio,
  Settings,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'simulator', label: 'Simulator', icon: Monitor },
  { id: 'flash', label: 'Build & Flash', icon: Zap },
  { id: 'serial', label: 'Serial Console', icon: Terminal },
  { id: 'mqtt', label: 'MQTT Debug', icon: Radio },
];

export function Sidebar({ activeView, onViewChange, collapsed, onToggleCollapse }) {
  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        {!collapsed && (
          <div className="sidebar-brand">
            <span className="brand-icon">⚡</span>
            <span className="brand-text">ESP32 Manager</span>
          </div>
        )}
        <button 
          className="collapse-btn"
          onClick={onToggleCollapse}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(item => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          
          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onViewChange(item.id)}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={20} className="nav-icon" />
              {!collapsed && <span className="nav-label">{item.label}</span>}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <button
          className="nav-item settings-btn"
          onClick={() => onViewChange('settings')}
          title={collapsed ? 'Settings' : undefined}
        >
          <Settings size={20} className="nav-icon" />
          {!collapsed && <span className="nav-label">Settings</span>}
        </button>
      </div>
    </aside>
  );
}
