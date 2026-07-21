import { useState } from "react";
import UploadPanel from "./components/UploadPanel.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:7860";

export default function App() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSelect = (selectedFile) => {
    setFile(selectedFile);
    setPreviewUrl(URL.createObjectURL(selectedFile));
    setResult(null);
    setError(null);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${res.status})`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err.message || "Something went wrong reaching the classifier.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="header">
        <h1 className="header__title">
          Gram Stain <span className="header__accent">Classifier</span>
        </h1>
        <p className="header__subtitle">
          Cellpose 2.0 segmentation + 5-vote per-cell classification
        </p>
      </header>

      <main className="panel">
        <UploadPanel onSelect={handleSelect} previewUrl={previewUrl} disabled={loading} />

        <button
          className="analyze-btn"
          onClick={handleAnalyze}
          disabled={!file || loading}
        >
          {loading ? "Analysing…" : "Analyse image"}
        </button>

        {error && <p className="error-msg">{error}</p>}

        <ResultsPanel result={result} />
      </main>

      <footer className="footer">
        Backend: Cellpose 2.0 (cyto2) + 5-vote classifier · hosted on Hugging Face Spaces
      </footer>
    </div>
  );
}
