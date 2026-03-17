# 🏦 Secure Financial Advisory Agent

An AI-powered financial advisory agent built with **LangGraph**, featuring privacy protection (Presidio PII detection), regulatory compliance checking, real-time market data, RAG-based knowledge retrieval, and a modern React frontend.

![Architecture](https://img.shields.io/badge/Architecture-LangGraph_Agent-blue)
![Privacy](https://img.shields.io/badge/Privacy-Presidio_PII-green)
![Market Data](https://img.shields.io/badge/Data-YFinance_Free-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Deployment](#-deployment)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Testing](#-testing)
- [Security Features Deep Dive](#-security-features-deep-dive)
- [Contributing](#-contributing)

---

## ✨ Features

### 🤖 AI Agent (LangGraph)

- **Multi-tool orchestration**: Automatically routes queries to the right tool
- **Conversation context**: Maintains chat history for contextual responses
- **State machine architecture**: Predictable, debuggable agent flow

### 📚 RAG (Retrieval-Augmented Generation)

- **ChromaDB vector store**: Fast similarity search
- **Free embeddings**: Uses `all-MiniLM-L6-v2` (no API cost)
- **Document upload**: Ingest PDFs, TXT, and MD files
- **Pre-seeded knowledge**: Asset allocation, retirement planning, tax strategies, risk metrics, compliance

### 📊 Real-Time Market Data

- **YFinance integration**: Free, no API key needed
- **Stock quotes**: Price, P/E, market cap, 52-week range, dividends
- **Market overview**: S&P 500, Dow, NASDAQ, Russell 2000, VIX
- **Volume & performance metrics**

### 🧮 Financial Calculator

- **Compound interest**: FV with configurable compounding
- **Loan/mortgage payments**: Monthly payment, total interest
- **Investment returns**: CAGR, total return
- **Retirement projections**: Based on 4% rule
- **Safe math evaluation**: Sandboxed, no code injection

### 🔒 Privacy Protection

- **PII Detection**: SSN, credit cards, bank accounts, phone numbers, emails (Presidio)
- **Auto-anonymization**: Strips PII before LLM processing
- **Prompt injection guard**: Pattern-based detection of 20+ attack vectors
- **Output sanitization**: Removes leaked system prompts, adds disclaimers
- **Audit logging**: Every interaction logged for compliance

### ⚖️ Compliance Engine

- **Prohibited claims detection**: "Guaranteed returns", "no risk", etc.
- **Disclaimer injection**: Automatic disclaimers for investment/tax advice
- **Suitability checks**: Ensures recommendations consider risk tolerance
- **YAML-configurable rules**: Easy to customize for your jurisdiction

---

## 🏗 Architecture

┌─────────────────────────────┐
│ React Frontend │
│ (Vercel / Docker) │
└──────────┬──────────────────┘
│ REST API
┌──────────▼──────────────────┐
│ FastAPI Backend │
│ │
│ ┌──────────────────────┐ │
│ │ Input Security │ │
│ │ • Rate Limiter │ │
│ │ • Prompt Guard │ │
│ │ • PII Anonymizer │ │
│ └──────────┬───────────┘ │
│ │ │
│ ┌──────────▼───────────┐ │
│ │ LangGraph Agent │ │
│ │ │ │
│ │ Router → Tools → │ │
│ │ Responder │ │
│ │ │ │
│ │ Tools: │ │
│ │ • RAG Search │ │
│ │ • Market Data │ │
│ │ • Calculator │ │
│ │ • Compliance │ │
│ └──────────┬───────────┘ │
│ │ │
│ ┌──────────▼───────────┐ │
│ │ Output Security │ │
│ │ • PII Check │ │
│ │ • Disclaimer Add │ │
│ │ • Audit Log │ │
│ └──────────────────────┘ │
│ │
│ Data: ChromaDB + SQLite │
└─────────────────────────────┘
