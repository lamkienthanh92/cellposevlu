import { useState } from "react";
import UploadPanel from "./components/UploadPanel.jsx";
import ResultsPanel from "./components/ResultsPanel.jsx";
import BatchResultsPanel from "./components/BatchResultsPanel.jsx";
import ImageDetailModal from "./components/ImageDetailModal.jsx";
import { exportExcel } from "./lib/exportExcel.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:7860";

export default function App() {
  const [mode, setMode] = useState("single"); // "single" | "batch"

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [batchFiles, setBatchFiles] = useState([]);

  const [result, setResult] = useState(null); // single-image result
  const [batchResults, setBatchResults] = useState(null); // { count, results }
  const [selected, setSelected] = useState(null); // batch card shown in modal

  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null);

  const resetOutputs = () => {
    setResult(null);
    setBatchResults(null);
    setSelected(null);
    setError(null);
  };

  const handleModeChange = (next) => {
    setMode(next);
    resetOutputs();
  };

  const handleSelectSingle = (selectedFile) => {
    setFile(selectedFile);
    setPreviewUrl(URL.createObjectURL(selectedFile));
    resetOutputs();
  };

  const handleSelectBatch = (files) => {
    setBatchFiles(files);
    resetOutputs();
  };

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      if (mode === "single") {
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(`${API_URL}/analyze`, { method: "POST", body: formData });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(detail.detail || `Request failed (${res.status})`);
        }
        setResult(await res.json());
      } else {
        if (!batchFiles.length) return;
        const formData = new FormData();
        batchFiles.forEach((f) => formData.append("files", f));
        const res = await fetch(`${API_URL}/analyze-batch`, { method: "POST", body: formData });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(detail.detail || `Request failed (${res.status})`);
        }
        setBatchResults(await res.json());
      }
    } catch (err) {
      setError(err.message || "Something went wrong reaching the classifier.");
    } finally {
      setLoading(false);
    }
  };

  const handleExportSingle = async () => {
    if (!result || result.total_cells === 0) return;
    setExporting(true);
    setError(null);
    try {
      await exportExcel(API_URL, [
        { filename: result.filename || file?.name || "image", features: result.features },
      ]);
    } catch (err) {
      setError(err.message || "Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const handleExportBatch = async () => {
    if (!batchResults?.results?.length) return;
    setExporting(true);
    setError(null);
    try {
      const rows = batchResults.results
        .filter((r) => r.features)
        .map((r) => ({ filename: r.filename, features: r.features }));
      await exportExcel(API_URL, rows);
    } catch (err) {
      setError(err.message || "Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const canAnalyze = mode === "single" ? !!file : batchFiles.length > 0;

  return (
    <div className="page">
      <header className="header">
        <h1 className="header__title">
          Gram Stain <span className="header__accent">Classifier</span>
        </h1>
        <p className="header__subtitle">
          Omnipose segmentation (round + elongated bacteria) + 5-vote per-cell classification
        </p>
      </header>

      <main className="panel">
        <UploadPanel
          mode={mode}
          onModeChange={handleModeChange}
          onSelectSingle={handleSelectSingle}
          onSelectBatch={handleSelectBatch}
          previewUrl={previewUrl}
          fileCount={batchFiles.length}
          disabled={loading}
        />

        <button className="analyze-btn" onClick={handleAnalyze} disabled={!canAnalyze || loading}>
          {loading
            ? "Analyzing…"
            : mode === "single"
            ? "Analyze image"
            : `Analyze ${batchFiles.length || ""} images`}
        </button>

        {error && <p className="error-msg">{error}</p>}

        {mode === "single" && (
          <ResultsPanel result={result} onExport={handleExportSingle} exporting={exporting} />
        )}

        {mode === "batch" && batchResults && (
          <BatchResultsPanel
            batchResults={batchResults}
            onSelect={setSelected}
            onExport={handleExportBatch}
            exporting={exporting}
          />
        )}
      </main>

      {selected && <ImageDetailModal result={selected} onClose={() => setSelected(null)} />}

      <footer className="footer">
        Backend: Omnipose (bact_phase_affinity) + 5-vote classifier · hosted on Hugging Face Spaces
      </footer>
    </div>
  );
}
