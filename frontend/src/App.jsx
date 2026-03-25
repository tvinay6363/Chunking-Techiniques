import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [files, setFiles] = useState([]);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([
    { text: "Hello! Upload your documents and I'll help you extract insights.", isAi: true }
  ]);
  const [isUploading, setIsUploading] = useState(false);
  const [isAsking, setIsAsking] = useState(false);
  const chatEndRef = useRef(null);

  const API_URL = "http://localhost:8000";

  useEffect(() => {
    fetchFiles();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchFiles = async () => {
    try {
      const resp = await fetch(`${API_URL}/files`);
      const data = await resp.json();
      setFiles(data.files || []);
    } catch (err) {
      console.error("Failed to fetch files:", err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });
      fetchFiles();
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Are you sure you want to delete ${filename}?`)) return;

    try {
      await fetch(`${API_URL}/delete/${filename}`, {
        method: "DELETE",
      });
      fetchFiles();
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!query.trim() || isAsking) return;

    const userMsg = query;
    setMessages(prev => [...prev, { text: userMsg, isAi: false }]);
    setQuery('');
    setIsAsking(true);

    const formData = new FormData();
    formData.append("question", userMsg);

    try {
      const resp = await fetch(`${API_URL}/ask`, {
        method: "POST",
        body: formData,
      });
      const data = await resp.json();
      setMessages(prev => [...prev, { text: data.answer, isAi: true }]);
    } catch (err) {
      setMessages(prev => [...prev, { text: "Error: Could not get a response from the AI.", isAi: true }]);
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div className="app-container">
      <div className="sidebar">
        <h1>DocQHub</h1>
        
        <label className="upload-area">
          <input type="file" hidden onChange={handleFileUpload} accept=".pdf,.docx" />
          <div className="upload-content">
            <svg className="file-icon" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <p>{isUploading ? "Uploading..." : "Click to upload PDF or DOCX"}</p>
          </div>
        </label>

        <div className="file-list">
          <h3>Your Documents ({files.length})</h3>
          {files.map((f, i) => (
            <div key={i} className="file-item">
              <div className="file-info">
                <svg className="file-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                </svg>
                <span>{f}</span>
              </div>
              <button className="delete-btn" onClick={() => handleDelete(f)} title="Delete document">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>
                </svg>
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="chat-main">
        <div className="chat-history">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.isAi ? 'ai' : 'user'}`}>
              {m.text}
            </div>
          ))}
          {isAsking && <div className="message ai">Thinking...</div>}
          <div ref={chatEndRef} />
        </div>

        <form className="chat-input-container" onSubmit={handleAsk}>
          <div className="input-wrapper">
            <input 
              type="text" 
              placeholder="Ask a question about your documents..." 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isAsking}
            />
            <button className="send-btn" disabled={isAsking}>
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default App;
