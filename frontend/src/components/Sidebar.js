import React from 'react';

const navItems = [
  { id: 'chat', icon: '💬', label: 'Chat Assistant' },
  { id: 'market', icon: '📊', label: 'Market Data' },
  { id: 'upload', icon: '📄', label: 'Upload Documents' },
];

const features = [
  { icon: '🔒', label: 'PII Protection' },
  { icon: '🛡️', label: 'Prompt Guard' },
  { icon: '⚖️', label: 'Compliance Engine' },
  { icon: '📈', label: 'Real-time Data' },
  { icon: '🧮', label: 'Financial Calc' },
  { icon: '📚', label: 'RAG Knowledge' },
];

function Sidebar({ activeView, onViewChange, onNewChat, messageCount }) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title">Navigation</div>
        <button className="new-chat-btn" onClick={onNewChat}>
          ✨ New Conversation
        </button>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">
          <div className="nav-section-title">Main</div>
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeView === item.id ? 'active' : ''}`}
              onClick={() => onViewChange(item.id)}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="nav-section">
          <div className="nav-section-title">Security Features</div>
          {features.map((item, i) => (
            <div key={i} className="nav-item" style={{ cursor: 'default', opacity: 0.7 }}>
              <span className="nav-item-icon">{item.icon}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-stats">
          <div className="stat-item">
            <div className="stat-value">{messageCount}</div>
            <div className="stat-label">Messages</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">6</div>
            <div className="stat-label">Tools</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;