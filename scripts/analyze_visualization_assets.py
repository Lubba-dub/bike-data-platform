from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "data" / "gold" / "exports"
OUTPUT_DIR = ROOT / "data" / "visualizations" / "analysis_assets"


def _safe_read_csv(file_name: str) -> pd.DataFrame:
    path = EXPORT_DIR / file_name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _safe_read_json(file_name: str) -> list[dict]:
    path = EXPORT_DIR / file_name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _setup_style() -> None:
    plt.style.use("ggplot")


def _save_brand_bike_count(df: pd.DataFrame) -> Path | None:
    if df.empty:
        return None
    counts = (
        df.groupby("brand_name", dropna=False)["bike_variant_id"]
        .count()
        .sort_values(ascending=False)
        .head(12)
    )
    fig, ax = plt.subplots(figsize=(12, 6))
    counts.plot(kind="bar", ax=ax, color="#d55e5e")
    ax.set_title("Top Brands by Bike Variants")
    ax.set_xlabel("Brand")
    ax.set_ylabel("Bike Variant Count")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    path = OUTPUT_DIR / "brand_bike_count.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _save_component_part_distribution(df: pd.DataFrame) -> Path | None:
    if df.empty:
        return None
    counts = (
        df.groupby("part_name", dropna=False)["component_catalog_id"]
        .count()
        .sort_values(ascending=True)
        .tail(12)
    )
    fig, ax = plt.subplots(figsize=(12, 7))
    counts.plot(kind="barh", ax=ax, color="#4c78a8")
    ax.set_title("Top Part Categories by Catalog Count")
    ax.set_xlabel("Component Catalog Count")
    ax.set_ylabel("Part Category")
    fig.tight_layout()
    path = OUTPUT_DIR / "component_part_distribution.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _save_brand_part_matrix(component_df: pd.DataFrame) -> Path | None:
    if component_df.empty:
        return None
    top_brands = (
        component_df.groupby("brand_name")["component_catalog_id"]
        .count()
        .sort_values(ascending=False)
        .head(10)
        .index
    )
    pivot = (
        component_df[component_df["brand_name"].isin(top_brands)]
        .pivot_table(index="brand_name", columns="part_key", values="component_catalog_id", aggfunc="count", fill_value=0)
        .sort_index()
    )
    if pivot.empty:
        return None
    fig, ax = plt.subplots(figsize=(14, 7))
    heatmap = ax.imshow(pivot.values, cmap="magma", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Brand vs Part Taxonomy Matrix")
    fig.colorbar(heatmap, ax=ax, label="Catalog Count")
    fig.tight_layout()
    path = OUTPUT_DIR / "brand_part_matrix_heatmap.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _save_heatmap_score_3d(heatmap_df: pd.DataFrame) -> Path | None:
    if heatmap_df.empty:
        return None
    plot_df = heatmap_df.dropna(subset=["price_score", "quality_score", "value_score"]).copy()
    if plot_df.empty:
        return None
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    scatter = ax.scatter(
        plot_df["price_score"],
        plot_df["quality_score"],
        plot_df["value_score"],
        c=plot_df["offer_count"].fillna(0),
        cmap="viridis",
        s=(plot_df["review_count"].fillna(0) + 1) * 18,
        alpha=0.82,
    )
    ax.set_xlabel("Price Score")
    ax.set_ylabel("Quality Score")
    ax.set_zlabel("Value Score")
    ax.set_title("3D Bike Part Metric Space")
    fig.colorbar(scatter, ax=ax, shrink=0.7, label="Offer Count")
    fig.tight_layout()
    path = OUTPUT_DIR / "bike_part_metric_3d.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _build_metric_space_from_parts_api(parts_api_rows: list[dict]) -> pd.DataFrame:
    rows = []
    for row in parts_api_rows:
        rows.append(
            {
                "bike_name": row.get("bike_name"),
                "brand": row.get("brand"),
                "part_key": row.get("part_key"),
                "component_name": row.get("component_name") or row.get("value"),
                "price_score": row.get("price_score"),
                "quality_score": row.get("quality_score"),
                "value_score": row.get("value_score"),
                "offer_count": row.get("offers_count"),
                "review_count": row.get("reviews_count"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for column in ["price_score", "quality_score", "value_score", "offer_count", "review_count"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _save_brand_growth_gif(bike_df: pd.DataFrame) -> Path | None:
    if bike_df.empty:
        return None
    counts = (
        bike_df.groupby("brand_name")["bike_variant_id"]
        .count()
        .sort_values(ascending=False)
        .head(8)
    )
    frames: list[Image.Image] = []
    temp_paths = []
    for step in range(1, len(counts) + 1):
        fig, ax = plt.subplots(figsize=(10, 6))
        partial = counts.iloc[:step]
        partial.plot(kind="bar", ax=ax, color="#ef8a62")
        ax.set_ylim(0, max(counts.max() * 1.15, 1))
        ax.set_title(f"Brand Coverage Build-up ({step}/{len(counts)})")
        ax.set_xlabel("Brand")
        ax.set_ylabel("Bike Variant Count")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        temp_path = OUTPUT_DIR / f"_brand_growth_{step:02d}.png"
        fig.savefig(temp_path, dpi=160)
        plt.close(fig)
        temp_paths.append(temp_path)
        frames.append(Image.open(temp_path).convert("RGB"))
    if not frames:
        return None
    gif_path = OUTPUT_DIR / "brand_growth.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=700, loop=0)
    for frame in frames:
        frame.close()
    for temp_path in temp_paths:
        temp_path.unlink(missing_ok=True)
    return gif_path


def _save_plotly_html(heatmap_df: pd.DataFrame) -> Path | None:
    if heatmap_df.empty:
        return None
    plot_df = heatmap_df.dropna(subset=["price_score", "quality_score", "value_score"]).copy()
    if plot_df.empty:
        return None
    plot_df = plot_df.head(160)
    data = [
        {
            "x": round(float(row["price_score"]), 4),
            "y": round(float(row["quality_score"]), 4),
            "z": round(float(row["value_score"]), 4),
            "name": row["component_name"] if isinstance(row["component_name"], str) else row["part_name"],
            "part": row["part_name"],
            "offers": 0 if pd.isna(row["offer_count"]) else int(row["offer_count"]),
            "reviews": 0 if pd.isna(row["review_count"]) else int(row["review_count"]),
        }
        for _, row in plot_df.iterrows()
    ]
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Bike Part Metric 3D Scatter</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{
      margin: 0;
      background: #0d1117;
      color: #f0f6fc;
      font-family: Arial, sans-serif;
    }}
    #plot {{
      width: 100vw;
      height: 100vh;
    }}
  </style>
</head>
<body>
  <div id="plot"></div>
  <script>
    const rows = {json.dumps(data, ensure_ascii=False)};
    const trace = {{
      type: 'scatter3d',
      mode: 'markers',
      x: rows.map(r => r.x),
      y: rows.map(r => r.y),
      z: rows.map(r => r.z),
      text: rows.map(r => `${{r.name}}<br>${{r.part}}<br>offers=${{r.offers}} reviews=${{r.reviews}}`),
      marker: {{
        size: rows.map(r => 4 + r.reviews * 0.35),
        color: rows.map(r => r.offers),
        colorscale: 'Turbo',
        opacity: 0.85,
        line: {{
          color: '#ffffff',
          width: 0.4
        }}
      }}
    }};
    const layout = {{
      title: 'Bike Part Metric 3D Scatter',
      paper_bgcolor: '#0d1117',
      plot_bgcolor: '#0d1117',
      scene: {{
        xaxis: {{title: 'Price Score'}},
        yaxis: {{title: 'Quality Score'}},
        zaxis: {{title: 'Value Score'}}
      }},
      font: {{color: '#f0f6fc'}}
    }};
    Plotly.newPlot('plot', [trace], layout, {{responsive: true}});
  </script>
</body>
</html>"""
    path = OUTPUT_DIR / "bike_part_metric_3d.html"
    path.write_text(html, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _setup_style()

    bike_df = _safe_read_csv("vw_bike_core.csv")
    component_df = _safe_read_csv("vw_component_core.csv")
    heatmap_df = _safe_read_csv("vw_bike_part_heatmap.csv")
    parts_api_rows = _safe_read_json("website_parts_api.json")
    metric_space_df = _build_metric_space_from_parts_api(parts_api_rows)

    outputs = {
        "brand_bike_count": _save_brand_bike_count(bike_df),
        "component_part_distribution": _save_component_part_distribution(component_df),
        "brand_part_matrix_heatmap": _save_brand_part_matrix(component_df),
        "bike_part_metric_3d": _save_heatmap_score_3d(metric_space_df if not metric_space_df.empty else heatmap_df),
        "brand_growth_gif": _save_brand_growth_gif(bike_df),
        "bike_part_metric_3d_html": _save_plotly_html(metric_space_df if not metric_space_df.empty else heatmap_df),
        "summary": {
            "bike_rows": int(len(bike_df)),
            "component_rows": int(len(component_df)),
            "heatmap_rows": int(len(heatmap_df)),
            "parts_api_rows": int(len(metric_space_df)),
            "brand_count": int(bike_df["brand_name"].nunique()) if not bike_df.empty else 0,
            "part_category_count": int(component_df["part_key"].nunique()) if not component_df.empty else 0,
        },
    }
    summary_path = OUTPUT_DIR / "analysis_assets_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                **outputs,
                "brand_bike_count": str(outputs["brand_bike_count"]) if outputs["brand_bike_count"] else None,
                "component_part_distribution": str(outputs["component_part_distribution"]) if outputs["component_part_distribution"] else None,
                "brand_part_matrix_heatmap": str(outputs["brand_part_matrix_heatmap"]) if outputs["brand_part_matrix_heatmap"] else None,
                "bike_part_metric_3d": str(outputs["bike_part_metric_3d"]) if outputs["bike_part_metric_3d"] else None,
                "brand_growth_gif": str(outputs["brand_growth_gif"]) if outputs["brand_growth_gif"] else None,
                "bike_part_metric_3d_html": str(outputs["bike_part_metric_3d_html"]) if outputs["bike_part_metric_3d_html"] else None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(summary_path)


if __name__ == "__main__":
    main()
