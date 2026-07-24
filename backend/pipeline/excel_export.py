"""
Builds the same multi-sheet Excel workbook as the original standalone
Colab batch script (Full_Data, SV1/SV2/SV3, Background_Info,
Summary_Statistics) from a list of per-image feature dicts, entirely
in memory. Used by POST /export-excel -- the frontend sends back the
features it already has (from /analyze or /analyze-batch), so no
image is re-processed just to produce the spreadsheet.
"""
import io

import pandas as pd


def build_excel_workbook(records: list[dict]) -> bytes:
    df = pd.DataFrame(records)
    buf = io.BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Full_Data", index=False)

        for prefix, sheet_name in (
            ("sv1_", "SV1_Intensity_30vars"),
            ("sv2_", "SV2_CellWall_30vars"),
            ("sv3_", "SV3_Morphology_30vars"),
        ):
            cols = ["filename"] + [c for c in df.columns if c.startswith(prefix)]
            df[cols].to_excel(writer, sheet_name=sheet_name, index=False)

        bg_cols = [c for c in
                   ["filename", "bg_r", "bg_g", "bg_b", "sv1_blue_bg_mean", "sv1_red_bg_mean"]
                   if c in df.columns]
        if bg_cols:
            df[bg_cols].to_excel(writer, sheet_name="Background_Info", index=False)

        valid_df = df[df["sv1_valid_cells"] > 0] if "sv1_valid_cells" in df.columns else df
        if len(valid_df) > 0:
            def avg(col):
                return valid_df[col].mean() if col in valid_df.columns else 0

            summary = pd.DataFrame({
                "Metric": [
                    "Total Images", "Images with Cells", "Avg Cells/Image",
                    "Avg Gram+ %", "Avg Gram- %", "Avg Area (um2)",
                    "Avg Circularity", "Avg Blue Intensity", "Avg Red Intensity",
                    "Avg Texture Roughness", "Avg Edge Sharpness",
                    "Avg Wall Thickness (um)", "Avg Membrane Integrity %",
                ],
                "Value": [
                    len(df), len(valid_df), avg("sv1_valid_cells"),
                    avg("sv3_gram_pos_pct"), avg("sv3_gram_neg_pct"),
                    avg("sv3_mean_area_um2"), avg("sv3_mean_circularity"),
                    avg("sv1_blue_mean"), avg("sv1_red_mean"),
                    avg("sv2_texture_roughness"), avg("sv2_edge_sharpness"),
                    avg("sv2_wall_thickness_mean"), avg("sv2_membrane_integrity_score"),
                ],
            })
            summary.to_excel(writer, sheet_name="Summary_Statistics", index=False)

    return buf.getvalue()
