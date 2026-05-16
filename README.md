# Remote Sensing Application: Fox Glacier Feature Tracking Lab

This repository contains a classroom lab for reproducing a Sentinel-2 optical feature-tracking workflow over Fox Glacier, New Zealand.

All teaching materials are in `FeatureTrackingLab/`.

## Lab Order

1. `1. plot_south_island_dem.ipynb`  
   Draw the South Island and Fox Glacier study-area map.

2. `2. optical_image_check.ipynb`  
   Search Sentinel-2 L2A scenes, check AOI cloud/snow conditions, and download B08 GeoTIFFs.

3. `3. fox_glacier_b08_autorift.ipynb`  
   Run autoRIFT feature tracking and save velocity results.

4. `4. run_streamlit_app_in_colab.ipynb`  
   Launch the Streamlit viewer in Colab.

The Streamlit app itself is `4. autorift_speed_scatter_app.py`.

## Notes

- Keep all files in `FeatureTrackingLab/` together.
- The notebooks save outputs into the same folder.
- Colab setup cells are included in the notebooks.
