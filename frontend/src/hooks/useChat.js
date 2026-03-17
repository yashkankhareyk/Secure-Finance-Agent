/**
 * Custom hook for chat functionality.
 * Manages messages, session state, and API communication.
 */

import { useState, useCallback, useRef } from 'react';
import { sendMessage } from '../services/api';

// Simple UUID generator (no external dependency)
function generateId() {
  return 'xxxx-xxxx-xxxx'.replace(/x/g, () =>
    Math.floor(Math.random() * 16).toString(16)
  );
}

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId] = useState(() => generateId());
  const abortControllerRef = useRef(null);

  const addMessage = useCallback((role, content, metadata = {}) => {
    const newMessage = {
      id: generateId(),
      role,
      content,
      timestamp: new Date().toISOString(),
      ...metadata,
    };
    setMessages((prev) => [...prev, newMessage]);
    return newMessage;
  }, []);

  const send = useCallback(
    async (userMessage) => {
      if (!userMessage.trim() || isLoading) return;

      setError(null);

      // Add user message
      addMessage('user', userMessage);

      // Add loading indicator
      const loadingId = generateId();
      setMessages((prev) => [
        ...prev,
        { id: loadingId, role: 'assistant', content: '', isLoading: true },
      ]);

      setIsLoading(true);

      try {
        const response = await sendMessage(userMessage, sessionId);

        // Replace loading message with actual response
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === loadingId
              ? {
                  ...msg,
                  content: response.response,
                  isLoading: false,
                  metadata: {
                    tools_used: response.tools_used,
                    route: response.route,
                    security: response.security,
                    processing_time_ms: response.processing_time_ms,
                    disclaimer_added: response.disclaimer_added,
                  },
                }
              : msg
          )
        );
      } catch (err) {
        // Replace loading message with error
        const errorMessage =
          err.response?.data?.detail ||
          err.message ||
          'Failed to get response. Please check if the backend is running.';

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === loadingId
              ? {
                  ...msg,
                  content: `⚠️ Error: ${errorMessage}`,
                  isLoading: false,
                  isError: true,
                }
              : msg
          )
        );
        setError(errorMessage);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, sessionId, addMessage]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sessionId,
    send,
    clearMessages,
  };
}