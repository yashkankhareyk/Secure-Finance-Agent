import React, { useState, useCallback } from 'react';
import { uploadDocument } from '../services/api';

function DocumentUpload() {
  const [uploads, setUploads] = useState([]);
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = useCallback(async (file) => {
    const allowedTypes = ['application/pdf', 'text/plain', 'text/markdown'];
    const allowedExtensions = ['.pdf', '.txt', '.md'];

    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      setUploads((prev) => [
        {
          name: file.name,
          status: 'error',
          message: 'Unsupported file type. Use PDF, TXT, or MD.',
        },
        ...prev,
      ]);
      return;
    }

    // Add uploading state
    const uploadId = Date.now();
    setUploads((prev) => [
      {
        id: uploadId,
        name: file.name,
        status: 'uploading',
        message: 'Uploading...',
      },
      ...prev,
    ]);

    try {
      const result = await uploadDocument(file);
      setUploads((prev) =>
        prev.map((u) =>
          u.id === uploadId
            ? {
                ...u,
                status: 'success',
                message: `${result.chunks_created} chunks created`,
              }
            : u
        )
      );
    } catch (err) {
      setUploads((prev) =>
        prev.map((u) =>
          u.id === uploadId
            ? {
                ...u,
                status: 'error',
                message: err.response?.data?.detail || 'Upload failed',
              }
            : u
        )
      );
    }
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      files.forEach(handleFile);
    },
    [handleFile]
  );

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleFileInput = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(handleFile);
    e.target.value = '';
  };

  return (
    <div className="upload-container">
      <div className="dashboard-header">
        <h1 className="dashboard-title">📄 Document Upload</h1>
        <p className="dashboard-subtitle">
          Upload financial reports, research papers, or compliance documents
          to enhance the AI's knowledge base via RAG.
        </p>
      </div>

      {/* Drop Zone */}
      <div
        className={`upload-zone ${isDragging ? 'active' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => document.getElementById('file-input').click()}
      >
        <div className="upload-icon">📁</div>
        <div className="upload-text">
          Drag & drop files here, or click to browse
        </div>
        <div className="upload-hint">
          Supported: PDF, TXT, MD • Max size: 10MB
        </div>
        <input
          id="file-input"
          type="file"
          accept=".pdf,.txt,.md"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileInput}
        />
      </div>

      {/* Upload List */}
      {uploads.length > 0 && (
        <div>
          <h3 style={{ marginBottom: '12px', fontSize: '16px' }}>
            Upload History
          </h3>
          <ul className="upload-list">
            {uploads.map((upload, i) => (
              <li key={upload.id || i} className="upload-item">
                <div className="upload-item-info">
                  <span>
                    {upload.status === 'success'
                      ? '✅'
                      : upload.status === 'error'
                      ? '❌'
                      : '⏳'}
                  </span>
                  <span>{upload.name}</span>
                </div>
                <span className={`upload-item-status ${upload.status}`}>
                  {upload.message}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Info Box */}
      <div
        style={{
          marginTop: '32px',
          padding: '20px',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
        }}
      >
        <h3 style={{ marginBottom: '12px', fontSize: '16px' }}>
          ℹ️ How Document Upload Works
        </h3>
        <ul style={{ paddingLeft: '20px', color: 'var(--text-secondary)', fontSize: '14px' }}>
          <li>Documents are split into chunks and converted to vector embeddings</li>
          <li>Embeddings are stored in ChromaDB for semantic search</li>
          <li>When you ask questions, the AI searches these documents for relevant context</li>
          <li>This is called Retrieval-Augmented Generation (RAG)</li>
          <li>All processing happens on the server - no data leaves your infrastructure</li>
        </ul>
      </div>
    </div>
  );
}

export default DocumentUpload;