import { useState } from "react";

const GROUPS = [
  { prefix: "sv1_", title: "SV1 — Intensity & staining" },
  { prefix: "sv2_", title: "SV2 — Cell-wall imaging proxies" },
  { prefix: "sv3_", title: "SV3 — Morphology & Gram classification" },
];

function FeatureGroup({ title, entries, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="feature-group">
      <button className="feature-group__toggle" onClick={() => setOpen(!open)}>
        <span>{title}</span>
        <span className="feature-group__count">{entries.length} vars</span>
      </button>
      {open && (
        <div className="feature-group__body">
          {entries.map(([key, value]) => (
            <div className="feature-row" key={key}>
              <span className="feature-row__key">{key.replace(/^sv[123]_/, "")}</span>
              <span className="feature-row__value">
                {typeof value === "number" ? value.toFixed(3) : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ResultsPanel({ result }) {
  if (!result) return null;

  if (result.total_cells === 0) {
    return (
      <div className="results">
        <p className="results__empty">{result.message}</p>
      </div>
    );
  }

  const { counts, percentages, total_cells, processing_time_seconds, features } = result;

  const rows = [
    { key: "gram_positive", label: "Gram-positive", swatch: "swatch--violet" },
    { key: "gram_negative", label: "Gram-negative / decolorised", swatch: "swatch--pink" },
    { key: "unclear", label: "Unclear (tie vote)", swatch: "swatch--neutral" },
  ];

  return (
    <div className="results">
      <div className="results__header">
        <span className="results__total">{total_cells}</span>
        <span className="results__total-label">cells detected</span>
      </div>

      <div className="results__bars">
        {rows.map((row) => (
          <div className="results__row" key={row.key}>
            <div className="results__row-label">
              <span className={`swatch ${row.swatch}`} />
              {row.label}
            </div>
            <div className="results__bar-track">
              <div
                className={`results__bar-fill ${row.swatch}`}
                style={{ width: `${percentages[row.key]}%` }}
              />
            </div>
            <div className="results__row-value">
              {counts[row.key]} <span className="results__pct">({percentages[row.key]}%)</span>
            </div>
          </div>
        ))}
      </div>

      {features && (
        <div className="feature-groups">
          <div className="feature-groups__header">
            <span className="feature-groups__title">
              Full profile — {Object.keys(features).length} variables
            </span>
            <button
              className="download-btn"
              onClick={() => downloadJson(result, "gram_analysis_result.json")}
            >
              Download JSON
            </button>
          </div>
          {GROUPS.map((g) => (
            <FeatureGroup
              key={g.prefix}
              title={g.title}
              entries={Object.entries(features).filter(([k]) => k.startsWith(g.prefix))}
              defaultOpen={false}
            />
          ))}
        </div>
      )}

      <div className="results__footer">
        Processed in {processing_time_seconds}s
      </div>
    </div>
  );
}
