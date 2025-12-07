import { useState } from 'react';

/**
 * CollapsibleSection - Expandable/collapsible content section
 * 
 * Features:
 * - Click header to expand/collapse
 * - Smooth animation
 * - Visual indicator for open/closed state
 */
export function CollapsibleSection({ title, icon, defaultOpen = false, children }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={`collapsible-section ${isOpen ? 'open' : 'closed'}`}>
      <button 
        className="collapsible-header"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span className="collapsible-title">
          {icon && <span className="section-icon">{icon}</span>}
          {title}
        </span>
        <span className={`collapsible-chevron ${isOpen ? 'open' : ''}`}>
          ▼
        </span>
      </button>
      <div className={`collapsible-content ${isOpen ? 'open' : ''}`}>
        <div className="collapsible-inner">
          {children}
        </div>
      </div>
    </div>
  );
}
