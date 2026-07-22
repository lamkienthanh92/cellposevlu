import { useState } from "react";
import UploadPanel from "./components/UploadPanel.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:7860";

export default function App() {
  const [files, setFiles] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(null); // { done, total, currentName }

  const handleSelect = (selectedFiles) => {
    setFiles(selectedFiles);
    setResults(null);
    setError(null);
    setProgress(null);
  };

  const analyzeOne = async (file) => {
    const formData = new FormData();
    formData.append("files", file);
    const res = await fetch(`${API_URL}/analyze`, { method: "POST", body: formData });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${file.name} failed (${res.status})`);
    }
    const data = await res.json();
    return data.results[0];
  };

  const handleAnalyze = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    setResults([]);
    setProgress({ done: 0, total: files.length, currentName: files[0].name });

    for (let i = 0; i < files.length; i++) {
      setProgress({ done: i, total: files.length, currentName: files[i].name });
      try {
        const result = await analyzeOne(files[i]);
        setResults((prev) => [...prev, result]);
      } catch (err) {
        setError(err.message || `Failed to analyse ${files[i].name}.`);
        setResults((prev) => [...prev, { filename: files[i].name, total_cells: 0, message: "Failed to analyse this image." }]);
      }
      setProgress({ done: i + 1, total: files.length, currentName: files[i].name });
    }

    setLoading(false);
  };

  const handleExportExcel = async () => {
    if (!files.length) return;
    setExporting(true);
    setError(null);
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      const res = await fetch(`${API_URL}/export-excel`, { method: "POST", body: formData });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Export failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "gram_analysis.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Something went wrong exporting the Excel file.");
    } finally {
      setExporting(false);
    }
  };

  const pct = progress ? Math.round((progress.done / progress.total) * 100) : 0;

  return (
    <div className="page">
      <header className="header">
        <h1 className="header__title">
          Gram Stain <span className="header__accent">Classifier</span>
        </h1>
        <p className="header__subtitle">
          Cellpose 2.0 segmentation + 5-vote per-cell classification — batch mode
        </p>
      </header>

      <main className="panel">
        <UploadPanel onSelect={handleSelect} files={files} disabled={loading || exporting} />

        <div className="action-row">
          <button className="analyze-btn" onClick={handleAnalyze} disabled={!files.length || loading}>
            {loading ? "Analysing…" : `Analyse ${files.length || ""} image(s)`}
          </button>
          <button
            className="analyze-btn analyze-btn--secondary"
            onClick={handleExportExcel}
            disabled={!files.length || exporting}
          >
            {exporting ? "Exporting…" : "Export to Excel"}
          </button>
        </div>

        {progress && (
          <div className="progress">
            <div className="progress__track">
              <div className="progress__fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="progress__label">
              <span>
                {progress.done}/{progress.total} images
              </span>
              {loading && <span className="progress__current">{progress.currentName}</span>}
              <span>{pct}%</span>
            </div>
          </div>
        )}

        {error && <p className="error-msg">{error}</p>}

        <ResultsPanel results={results} />
      </main>

      <footer className="footer">
        Backend: Cellpose 2.0 (cyto2) + 5-vote classifier · hosted on Hugging Face Spaces
      </footer>
    </div>
  );
}
