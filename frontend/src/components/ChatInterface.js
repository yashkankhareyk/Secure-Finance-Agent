import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';

const quickActions = [
  {
    icon: '📊',
    title: 'Market Overview',
    text: 'How is the stock market doing today?',
  },
  {
    icon: '💰',
    title: 'Investment Strategy',
    text: 'What is a good asset allocation strategy for a moderate risk investor?',
  },
  {
    icon: '🧮',
    title: 'Calculate Returns',
    text: 'Calculate compound interest on $10,000 at 7% annual rate for 20 years',
  },
  {
    icon: '📈',
    title: 'Stock Analysis',
    text: 'Get me the current stock data for AAPL',
  },
  {
    icon: '🎯',
    title: 'Retirement Planning',
    text: 'How much do I need saved for retirement with $60,000 annual expenses?',
  },
  {
    icon: '⚖️',
    title: 'Compliance Check',
    text: 'What are the SEC compliance requirements for investment advisors?',
  },
];

function ChatInterface({ chat }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat.messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !chat.isLoading) {
      chat.send(input.trim());
      setInput('');
    }
  };

  const handleQuickAction = (text) => {
    chat.send(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-container">
      {/* Messages Area */}
      <div className="chat-messages">
        {chat.messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-icon">🏦</div>
            <h1 className="welcome-title">SecureFinance AI</h1>
            <p className="welcome-subtitle">
              Your AI-powered financial advisor with privacy protection,
              real-time market data, and regulatory compliance built in.
            </p>
            <div className="quick-actions">
              {quickActions.map((action, i) => (
                <button
                  key={i}
                  className="quick-action"
                  onClick={() => handleQuickAction(action.text)}
                >
                  <span className="quick-action-icon">{action.icon}</span>
                  <div className="quick-action-text">
                    <div className="quick-action-title">{action.title}</div>
                    {action.text}
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {chat.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="chat-input-container">
        <form onSubmit={handleSubmit} className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about investments, market data, financial calculations..."
            disabled={chat.isLoading}
            rows={1}
          />
          <button
            type="submit"
            className="send-btn"
            disabled={!input.trim() || chat.isLoading}
          >
            {chat.isLoading ? '⏳' : '➤'}
          </button>
        </form>
        <div className="input-hint">
          🔒 Your data is protected with PII detection & anonymization.
          Press Enter to send, Shift+Enter for new line.
        </div>
      </div>
    </div>
  );
}

export default ChatInterface;