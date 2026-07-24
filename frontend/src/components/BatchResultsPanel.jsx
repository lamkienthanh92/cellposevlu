export default function BatchResultsPanel({ batchResults, onSelect, onExport, exporting }) {
  const { count, results } = batchResults;
  const withCells = results.filter((r) => r.total_cells > 0);
  const totalCells = withCells.reduce((sum, r) => sum + r.total_cells, 0);

  return (
    <div className="batch-results">
      <div className="batch-results__header">
        <div>
          <span className="results__total">{count}</span>
          <span className="results__total-label"> images · {totalCells} cells</span>
        </div>
        <button
          className="download-btn download-btn--excel"
          onClick={onExport}
          disabled={exporting || withCells.length === 0}
        >
          {exporting ? "Exporting…" : `Export Excel (90 variables × ${withCells.length} images)`}
        </button>
      </div>

      <div className="batch-grid">
        {results.map((r, idx) => (
          <button
            key={`${r.filename}-${idx}`}
            type="button"
            className="batch-card"
            onClick={() => r.total_cells > 0 && onSelect(r)}
            disabled={r.total_cells === 0}
          >
            {r.combined_image ? (
              <img src={r.combined_image} alt={r.filename} className="batch-card__thumb" />
            ) : (
              <div className="batch-card__thumb batch-card__thumb--empty" />
            )}
            <div className="batch-card__name" title={r.filename}>
              {r.filename}
            </div>
            {r.total_cells > 0 ? (
              <div className="batch-card__counts">
                <span className="swatch swatch--violet" /> {r.counts.gram_positive}
                <span className="swatch swatch--pink" /> {r.counts.gram_negative}
                <span className="swatch swatch--neutral" /> {r.counts.unclear}
              </div>
            ) : (
              <div className="batch-card__empty">No cells detected</div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
