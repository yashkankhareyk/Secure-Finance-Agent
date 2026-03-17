import React, { useState, useEffect } from 'react';

const watchlist = [
  { symbol: 'AAPL', name: 'Apple Inc.' },
  { symbol: 'GOOGL', name: 'Alphabet Inc.' },
  { symbol: 'MSFT', name: 'Microsoft Corp.' },
  { symbol: 'AMZN', name: 'Amazon.com Inc.' },
  { symbol: 'TSLA', name: 'Tesla Inc.' },
  { symbol: 'NVDA', name: 'NVIDIA Corp.' },
];

function MarketDashboard({ onAskAgent }) {
  const [selectedStock, setSelectedStock] = useState(null);

  const handleStockClick = (symbol) => {
    setSelectedStock(symbol);
    onAskAgent(`Get me the current stock data and analysis for ${symbol}`);
  };

  const handleOverview = () => {
    onAskAgent('Give me a market overview with major indices performance today');
  };

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1 className="dashboard-title">📊 Market Dashboard</h1>
        <p className="dashboard-subtitle">
          Click on any stock or action to get AI-powered analysis
        </p>
      </div>

      {/* Quick Actions */}
      <div className="dashboard-grid" style={{ marginBottom: '32px' }}>
        <div
          className="dashboard-card"
          style={{ cursor: 'pointer' }}
          onClick={handleOverview}
        >
          <div className="card-label">Market Overview</div>
          <div className="card-value" style={{ fontSize: '20px', color: 'var(--accent-primary)' }}>
            📈 Get Today's Overview
          </div>
          <div className="card-change" style={{ color: 'var(--text-muted)' }}>
            S&P 500, Dow, NASDAQ, VIX
          </div>
        </div>

        <div
          className="dashboard-card"
          style={{ cursor: 'pointer' }}
          onClick={() => onAskAgent('What sectors are performing best today and why?')}
        >
          <div className="card-label">Sector Analysis</div>
          <div className="card-value" style={{ fontSize: '20px', color: 'var(--accent-purple)' }}>
            🏭 Sector Performance
          </div>
          <div className="card-change" style={{ color: 'var(--text-muted)' }}>
            Technology, Healthcare, Finance...
          </div>
        </div>

        <div
          className="dashboard-card"
          style={{ cursor: 'pointer' }}
          onClick={() => onAskAgent('What is the current VIX level and what does it mean for market volatility?')}
        >
          <div className="card-label">Volatility</div>
          <div className="card-value" style={{ fontSize: '20px', color: 'var(--accent-warning)' }}>
            📉 VIX Analysis
          </div>
          <div className="card-change" style={{ color: 'var(--text-muted)' }}>
            Fear & Greed indicator
          </div>
        </div>
      </div>

      {/* Watchlist */}
      <h2 style={{ marginBottom: '16px', fontSize: '18px' }}>
        ⭐ Watchlist
      </h2>
      <div className="dashboard-grid">
        {watchlist.map((stock) => (
          <div
            key={stock.symbol}
            className="dashboard-card"
            style={{ cursor: 'pointer' }}
            onClick={() => handleStockClick(stock.symbol)}
          >
            <div className="card-label">{stock.name}</div>
            <div className="card-value" style={{ fontSize: '22px' }}>
              {stock.symbol}
            </div>
            <div className="card-change" style={{ color: 'var(--accent-primary)' }}>
              Click for live data & analysis →
            </div>
          </div>
        ))}
      </div>

      {/* Custom stock input */}
      <div style={{ marginTop: '32px' }}>
        <h2 style={{ marginBottom: '16px', fontSize: '18px' }}>
          🔍 Look Up Any Stock
        </h2>
        <div style={{ display: 'flex', gap: '12px', maxWidth: '400px' }}>
          <input
            type="text"
            placeholder="Enter ticker (e.g., META)"
            style={{
              flex: 1,
              padding: '12px 16px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              color: 'var(--text-primary)',
              fontSize: '14px',
              outline: 'none',
              textTransform: 'uppercase',
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.target.value.trim()) {
                onAskAgent(`Get me the current stock data for ${e.target.value.trim().toUpperCase()}`);
                e.target.value = '';
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}

export default MarketDashboard;