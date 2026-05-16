# Fox Glacier Feature Tracking Lab

This repository contains a classroom lab for reproducing a Sentinel-2 optical feature-tracking workflow over Fox Glacier, New Zealand.

All teaching files are in `FeatureTrackingLab/`.

## Recommended: GitHub Codespaces

1. Open this repository on GitHub.
2. Click **Code** → **Codespaces** → **Create codespace on main**.
3. Wait until the Codespace finishes building. The setup creates a conda environment named `rsa-lab`.
4. Open each notebook and choose the Jupyter kernel:

   ```text
   Python (rsa-lab)
   ```

The Codespaces configuration installs GMT, GDAL, PyGMT, rasterio, autoRIFT, Streamlit, and the other Python packages used in the lab.

The first Codespaces build can take several minutes. If a notebook reports missing packages, switch its kernel to `Python (rsa-lab)`.

## Lab Order

Run the notebooks in this order:

1. `FeatureTrackingLab/1. plot_south_island_dem.ipynb`  
   Draw the South Island and Fox Glacier study-area map.

2. `FeatureTrackingLab/2. optical_image_check.ipynb`  
   Search Sentinel-2 L2A scenes, check AOI cloud/snow conditions, and download B08 GeoTIFFs.

3. `FeatureTrackingLab/3. fox_glacier_b08_autorift.ipynb`  
   Run autoRIFT feature tracking and save velocity results.

## Interactive Viewer

After Part 3 finishes, run the Streamlit viewer from the Codespaces terminal:

```bash
cd FeatureTrackingLab
streamlit run "4. autorift_speed_scatter_app.py"
```

Codespaces will show a forwarded port for Streamlit. Open the forwarded `8501` port in the browser.

## Notes

- Keep all files in `FeatureTrackingLab/` together.
- The notebooks save generated outputs into `FeatureTrackingLab/`.
- Generated files such as `.tif`, `.png`, `.npz`, `.nc`, and `.cpt` are ignored by Git.
