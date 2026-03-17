import React, { useState, useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import Sidebar from './components/Sidebar';
import MarketDashboard from './components/MarketDashboard';
import DocumentUpload from './components/DocumentUpload';
import SecurityBadge from './components/SecurityBadge';
import { useChat } from './hooks/useChat';
import { checkHealth } from './services/api';
import './App.css';

function App() {
  const [activeView, setActiveView] = useState('chat');
  const [backendStatus, setBackendStatus] = useState('checking');
  const [healthData, setHealthData] = useState(null);
  const chat = useChat();

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const data = await checkHealth();
        setBackendStatus('connected');
        setHealthData(data);
      } catch (err) {
        setBackendStatus('disconnected');
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 30000);
    return () => clearInterval(interval);
  }, []);

  const renderMainContent = () => {
    switch (activeView) {
      case 'chat':
        return <ChatInterface chat={chat} />;
      case 'market':
        return <MarketDashboard onAskAgent={(q) => { setActiveView('chat'); chat.send(q); }} />;
      case 'upload':
        return <DocumentUpload />;
      default:
        return <ChatInterface chat={chat} />;
    }
  };

  return (
    <div className="app">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        onNewChat={chat.clearMessages}
        messageCount={chat.messages.length}
      />

      <div className="app-main">
        {/* Header */}
        <header className="app-header">
          <div className="header-left">
            <span className="header-logo">🏦</span>
            <div>
              <div className="header-title">SecureFinance AI</div>
              <div className="header-subtitle">
                {healthData ? `${healthData.llm_provider} • ${healthData.documents_loaded} docs loaded` : 'Connecting...'}
              </div>
            </div>
          </div>
          <div className="header-right">
            <SecurityBadge status={backendStatus} />
            <span className="header-badge badge-ai">🤖 AI Agent</span>
            <span className="header-badge badge-secure">🔒 Encrypted</span>
          </div>
        </header>

        {/* Main Content */}
        {renderMainContent()}
      </div>
    </div>
  );
}

export default App;