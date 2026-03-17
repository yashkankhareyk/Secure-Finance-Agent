import React, { useState } from 'react';

function PortfolioAnalyzer({ onAskAgent }) {
  const [holdings, setHoldings] = useState([
    { symbol: '', shares: '', price: '' },
  ]);

  const addHolding = () => {
    setHoldings([...holdings, { symbol: '', shares: '', price: '' }]);
  };

  const updateHolding = (index, field, value) => {
    const updated = [...holdings];
    updated[index][field] = value;
    setHoldings(updated);
  };

  const analyzePortfolio = () => {
    const validHoldings = holdings.filter((h) => h.symbol && h.shares);
    if (validHoldings.length === 0) return;

    const query = `Analyze my portfolio: ${validHoldings
      .map((h) => `${h.shares} shares of ${h.symbol.toUpperCase()}`)
      .join(', ')}. What is the total value, diversification, and risk assessment?`;

    onAskAgent(query);
  };

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1 className="dashboard-title">📁 Portfolio Analyzer</h1>
        <p className="dashboard-subtitle">
          Enter your holdings for AI-powered analysis
        </p>
      </div>

      <div style={{ maxWidth: '600px' }}>
        {holdings.map((holding, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              gap: '12px',
              marginBottom: '12px',
              alignItems: 'center',
            }}
          >
            <input
              placeholder="Symbol (e.g. AAPL)"
              value={holding.symbol}
              onChange={(e) => updateHolding(i, 'symbol', e.target.value)}
              style={{
                flex: 2,
                padding: '12px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
                fontSize: '14px',
                textTransform: 'uppercase',
                outline: 'none',
              }}
            />
            <input
              placeholder="Shares"
              type="number"
              value={holding.shares}
              onChange={(e) => updateHolding(i, 'shares', e.target.value)}
              style={{
                flex: 1,
                padding: '12px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
                fontSize: '14px',
                outline: 'none',
              }}
            />
          </div>
        ))}

        <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
          <button
            onClick={addHolding}
            style={{
              padding: '10px 20px',
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            + Add Holding
          </button>
          <button
            onClick={analyzePortfolio}
            style={{
              padding: '10px 24px',
              background: 'var(--accent-primary)',
              border: 'none',
              borderRadius: '8px',
              color: 'white',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '600',
            }}
          >
            🔍 Analyze Portfolio
          </button>
        </div>
      </div>
    </div>
  );
}

export default PortfolioAnalyzer;