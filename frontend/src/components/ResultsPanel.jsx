import { useState } from "react";

const GROUPS = [
  { prefix: "sv1_", title: "SV1 — Intensity & staining" },
  { prefix: "sv2_", title: "SV2 — Cell-wall imaging proxies" },
  { prefix: "sv3_", title: "SV3 — Morphology & Gram classification" },
];

function FeatureGroup({ title, entries }) {
  const [open, setOpen] = useState(false);
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

function ImageCard({ label, src }) {
  return (
    <div className="image-card">
      <span className="image-card__label">{label}</span>
      {src ? (
        <img src={`data:image/png;base64,${src}`} alt={label} className="image-card__img" />
      ) : (
        <div className="image-card__placeholder">n/a</div>
      )}
    </div>
  );
}

function OneResult({ result }) {
  const [open, setOpen] = useState(true);

  if (result.total_cells === 0) {
    return (
      <div className="result-card">
        <div className="result-card__header">
          <span className="result-card__filename">{result.filename}</span>
          <span className="results__empty">{result.message}</span>
        </div>
      </div>
    );
  }

  const { counts, percentages, total_cells, processing_time_seconds, features, images } = result;

  const rows = [
    { key: "gram_positive", label: "Gram-positive", swatch: "swatch--violet" },
    { key: "gram_negative", label: "Gram-negative / decolorised", swatch: "swatch--pink" },
    { key: "unclear", label: "Unclear (tie vote)", swatch: "swatch--neutral" },
  ];

  return (
    <div className="result-card">
      <button className="result-card__header" onClick={() => setOpen(!open)}>
        <span className="result-card__filename">{result.filename}</span>
        <span className="result-card__summary">
          {total_cells} cells · {processing_time_seconds}s
        </span>
      </button>

      {open && (
        <div className="result-card__body">
          <div className="image-row">
            <ImageCard label="Original" src={images?.original} />
            <ImageCard label="Segmented" src={images?.segmented} />
            <ImageCard label="Gram-classified" src={images?.gram_classified} />
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
              <span className="feature-groups__title">
                Full profile — {Object.keys(features).length} variables
              </span>
              {GROUPS.map((g) => (
                <FeatureGroup
                  key={g.prefix}
                  title={g.title}
                  entries={Object.entries(features).filter(([k]) => k.startsWith(g.prefix))}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ResultsPanel({ results }) {
  if (!results || results.length === 0) return null;
  return (
    <div className="results">
      {results.map((r, i) => (
        <OneResult result={r} key={r.filename + i} />
      ))}
    </div>
  );
}
