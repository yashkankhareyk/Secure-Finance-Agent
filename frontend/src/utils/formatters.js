/**
 * Utility functions for formatting data.
 */

export function formatCurrency(value) {
  if (value === null || value === undefined || value === 'N/A') return 'N/A';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(num);
}

export function formatNumber(value) {
  if (value === null || value === undefined) return 'N/A';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return 'N/A';
  return new Intl.NumberFormat('en-US').format(num);
}

export function formatPercent(value) {
  if (value === null || value === undefined) return 'N/A';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return 'N/A';
  return `${(num * 100).toFixed(2)}%`;
}

export function formatTimestamp(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatProcessingTime(ms) {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function getRouteIcon(route) {
  const icons = {
    rag: '📚',
    market: '📊',
    calculator: '🧮',
    compliance: '⚖️',
    general: '💬',
    blocked: '🛡️',
    error: '⚠️',
  };
  return icons[route] || '💬';
}

export function getRouteLabel(route) {
  const labels = {
    rag: 'Knowledge Base',
    market: 'Market Data',
    calculator: 'Calculator',
    compliance: 'Compliance',
    general: 'General',
    blocked: 'Blocked',
    error: 'Error',
  };
  return labels[route] || route;
}