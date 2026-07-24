/**
 * Sends {filename, features} rows to the backend and downloads the
 * resulting multi-sheet .xlsx (Full_Data, SV1/SV2/SV3,
 * Background_Info, Summary_Statistics — same layout as the
 * standalone batch script). No image is re-processed here: the
 * features were already computed by /analyze or /analyze-batch.
 */
export async function exportExcel(apiUrl, rows) {
  const res = await fetch(`${apiUrl}/export-excel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows }),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Export failed (${res.status})`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "gram_analysis_90vars.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
