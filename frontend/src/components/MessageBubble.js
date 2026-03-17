import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { formatProcessingTime, getRouteIcon, getRouteLabel } from '../utils/formatters';

function MessageBubble({ message }) {
  const { role, content, isLoading, isError, metadata } = message;

  if (isLoading) {
    return (
      <div className="message assistant">
        <div className="message-avatar">🤖</div>
        <div className="message-content">
          <div className="loading-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`message ${role} ${isError ? 'error' : ''}`}>
      <div className="message-avatar">
        {role === 'user' ? '👤' : '🤖'}
      </div>
      <div>
        <div className="message-content">
          {role === 'user' ? (
            <p>{content}</p>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          )}
        </div>

        {/* Metadata tags */}
        {metadata && role === 'assistant' && (
          <div className="message-meta">
            {metadata.route && metadata.route !== 'unknown' && (
              <span className="meta-tag route">
                {getRouteIcon(metadata.route)} {getRouteLabel(metadata.route)}
              </span>
            )}
            {metadata.processing_time_ms && (
              <span className="meta-tag time">
                ⏱ {formatProcessingTime(metadata.processing_time_ms)}
              </span>
            )}
            {metadata.security?.pii_found_in_input > 0 && (
              <span className="meta-tag warning">
                🔒 PII Redacted
              </span>
            )}
            {metadata.security?.input_safe && (
              <span className="meta-tag security">
                ✅ Verified
              </span>
            )}
            {metadata.tools_used?.length > 0 && (
              <span className="meta-tag route">
                🔧 {metadata.tools_used.join(', ')}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default MessageBubble;