import React from 'react';

function SecurityBadge({ status }) {
  const getStatusInfo = () => {
    switch (status) {
      case 'connected':
        return { color: 'green', text: 'Secure Connection' };
      case 'disconnected':
        return { color: 'red', text: 'Backend Offline' };
      default:
        return { color: 'yellow', text: 'Connecting...' };
    }
  };

  const info = getStatusInfo();

  return (
    <div className="security-badge-container">
      <span className={`security-dot ${info.color}`}></span>
      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
        {info.text}
      </span>
    </div>
  );
}

export default SecurityBadge;