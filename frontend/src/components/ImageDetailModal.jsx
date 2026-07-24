import { useState } from "react";

const GROUPS = [
  { prefix: "sv1_", title: "SV1 — Intensity & staining" },
  { prefix: "sv2_", title: "SV2 — Cell-wall imaging proxies" },
  { prefix: "sv3_", title: "SV3 — Morphology & Gram classification" },
];

const TABS = [
  { key: "original", label: "Ảnh gốc" },
  { key: "segmentation", label: "Segmentation" },
  { key: "gram", label: "Gram classification" },
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

export default function ImageDetailModal({ result, onClose }) {
  const [tab, setTab] = useState("original");
  const { filename, total_cells, counts, percentages, features, images } = result;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <h2 title={filename}>{filename}</h2>
          <button className="modal__close" onClick={onClose} aria-label="Đóng">
            ✕
          </button>
        </div>

        <div className="modal__tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`modal__tab ${tab === t.key ? "modal__tab--active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="modal__image-wrap">
          <img src={images[tab]} alt={tab} className="modal__image" />
        </div>

        <div className="modal__summary">
          <span>{total_cells} tế bào</span>
          <span className="modal__summary-item">
            <span className="swatch swatch--violet" /> Gram+ {counts.gram_positive} ({percentages.gram_positive}%)
          </span>
          <span className="modal__summary-item">
            <span className="swatch swatch--pink" /> Gram- {counts.gram_negative} ({percentages.gram_negative}%)
          </span>
          <span className="modal__summary-item">
            <span className="swatch swatch--neutral" /> Unclear {counts.unclear} ({percentages.unclear}%)
          </span>
        </div>

        {features && (
          <div className="feature-groups">
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
    </div>
  );
}
