# Fox Glacier Feature Tracking Lab 复现指南

本文档记录 Fox Glacier feature tracking lab 的复现流程：打开 GitHub Codespaces，依次运行 notebook，并使用 Streamlit 查看最终结果。

文档中的图片占位可替换为运行过程和结果截图。

## 1. 打开 GitHub Codespaces

1. 在浏览器中打开 GitHub 仓库。
2. 点击 `Code` -> `Codespaces` -> `Create codespace on main`。
3. 等待 Codespace 完成环境构建。第一次构建会安装地理空间环境，可能需要几分钟。
4. 打开 `FeatureTrackingLab/` 文件夹。
5. 打开每个 notebook 后，选择内核：

```text
Python (rsa-lab)
```

图片占位：

```markdown
![Codespaces start page](images/codespaces_start.png)
![Kernel selection](images/kernel_selection.png)
```

环境由 `.devcontainer/environment.yml` 创建。若暂时看不到 `Python (rsa-lab)`，等待环境安装完成后刷新页面。

## 2. 文件运行顺序

按下面顺序运行：

1. `1. plot_south_island_dem.ipynb`
2. `2. optical_image_check.ipynb`
3. `3. fox_glacier_b08_autorift.ipynb`
4. `4. run_streamlit_viewer.ipynb`

主要固定输入文件：

- `fox_glacier_from_osm.geojson`：Fox Glacier 边界。
- `earth_relief_30s_south_island.nc`：Part 1 使用的 South Island DEM 子集。
- `4. autorift_speed_scatter_app.py`：Part 4 调用的 Streamlit 程序。

生成结果保存在 `FeatureTrackingLab/` 当前文件夹中。`.tif`、`.png`、`.npz`、`.cpt` 和大多数 `.nc` 文件已在 `.gitignore` 中忽略。

## 3. Part 1: Research Area Map

Notebook:

```text
1. plot_south_island_dem.ipynb
```

目标：

- 绘制 South Island 研究区总览图。
- 绘制 Fox Glacier 局部 inset 图。
- 保存结果：

```text
south_island_dem.png
```

代码逻辑：

1. 读取本地 DEM 子集 `earth_relief_30s_south_island.nc`。
2. 使用 PyGMT 绘制 South Island 地形图。
3. 使用 Contextily 和 GDAL 生成 Fox Glacier 局部底图。
4. 添加冰川范围框、城市标注、比例尺、指北针、panel 标签和连接线。
5. 保存最终 PNG。

图片占位：

```markdown
![Part 1 research area map](images/part1_research_area.png)
```

可调参数：

| 参数 | 当前值 | 作用 |
|---|---:|---|
| `R_LEFT` | `[166.0, 174.5, -47.5, -40.3]` | South Island 总览图范围，顺序为 west, east, south, north |
| `FOX_W, FOX_E, FOX_S, FOX_N` | `170.0, 170.2, -43.62, -43.42` | Fox Glacier 局部图范围 |
| `TILE_ZOOM` | `14` | 局部底图缩放级别，越大越清晰，但下载和处理更慢 |
| `GAP_CM` | `0.45` | 左右两个 panel 之间的间距 |
| `LEFT_FONT_ANNOT` | `"10p"` | 左侧总览图坐标轴字体大小 |
| `LABEL_PANEL` | `"18p,Helvetica-Bold,black"` | panel 标签字体 |
| `LEFT_MAP_SCALE` | `"jBR+w200k+o0.65c/0.75c"` | 左侧总览图比例尺 |
| `RIGHT_MAP_SCALE` | `"jBR+w2k+o0.65c/0.75c"` | 右侧局部图比例尺 |

字体大小相关位置：

```python
fig.text(..., font="12p,Helvetica-Bold,black")
LABEL_PANEL = "18p,Helvetica-Bold,black"
LEFT_FONT_ANNOT = "10p"
```

地图范围相关位置：

```python
R_LEFT = [166.0, 174.5, -47.5, -40.3]
FOX_W, FOX_E, FOX_S, FOX_N = 170.0, 170.2, -43.62, -43.42
```

## 4. Part 2: Optical Image Check and Download

Notebook:

```text
2. optical_image_check.ipynb
```

目标：

- 从 Microsoft Planetary Computer 搜索 Sentinel-2 L2A 影像。
- 用 Sentinel-2 SCL 波段计算 AOI 内的云量和雪量。
- 根据阈值筛选影像。
- 保存 quicklook 图。
- 下载选定日期的 B08 近红外 GeoTIFF，用于 Part 3 feature tracking。

输出：

```text
fox_glacier_b08_quicklook.png
fox_glacier_b08_quicklook_dates.png
B08_fox_2026-03-01.tif
B08_fox_2026-03-21.tif
```

代码逻辑：

1. 读取 `fox_glacier_from_osm.geojson`。
2. 根据冰川边界生成带 buffer 的 AOI bbox。
3. 在设定日期范围内搜索 Sentinel-2 L2A 影像。
4. 读取每景影像的 SCL chip。
5. 计算 AOI 内 cloud 和 snow 百分比。
6. 删除云量或雪量超过阈值的影像。
7. 生成所有通过筛选影像的 quicklook。
8. 下载 `DOWNLOAD_DATES` 指定日期的 B08 GeoTIFF。

图片占位：

```markdown
![Part 2 all AOI-clear quicklook](images/part2_quicklook_all.png)
![Part 2 selected dates quicklook](images/part2_quicklook_dates.png)
```

主要参数：

| 参数 | 当前值 | 作用 |
|---|---:|---|
| `PRESET_DATETIME` | `2022-01-01T00:00:00Z/2026-12-31T23:59:59Z` | STAC 搜索日期范围 |
| `DOWNLOAD_DATES` | `["20260301", "20260321"]` | 下载用于 feature tracking 的日期 |
| `PRESET_BUFFER_DEG` | `0.02` | AOI bbox 外扩范围，单位是经纬度 |
| `PRESET_SCL_CLOUD_CLASSES` | `(3, 8, 9, 10)` | 被视为 cloud/shadow/cirrus 的 SCL 类别 |
| `PRESET_SCL_SNOW_CLASSES` | `(11,)` | 被视为 snow/ice 的 SCL 类别 |
| `PRESET_MAX_AOI_CLOUD_PCT` | `10.0` | AOI 内最大允许云量百分比 |
| `PRESET_MAX_AOI_SNOW_PCT` | `40.0` | AOI 内最大允许雪量百分比 |
| `PRESET_STAC_SCENE_CLOUD_LT` | `None` | 可选的整景云量过滤 |
| `PRESET_LIMIT` | `None` | 可选的 STAC 返回数量上限 |

修改搜索日期范围：

```python
PRESET_DATETIME = "2022-01-01T00:00:00Z/2026-12-31T23:59:59Z"
```

修改下载日期：

```python
DOWNLOAD_DATES = ["20260301", "20260321"]
```

`DOWNLOAD_DATES` 应该落在 `PRESET_DATETIME` 的搜索范围内，并且对应日期需要有通过 cloud/snow 筛选的 Sentinel-2 影像。

修改云量和雪量阈值：

```python
PRESET_MAX_AOI_CLOUD_PCT = 10.0
PRESET_MAX_AOI_SNOW_PCT = 40.0
```

阈值越低，筛选越严格，可用日期通常越少；阈值越高，可用日期通常越多。

## 5. Part 3: autoRIFT Feature Tracking

Notebook:

```text
3. fox_glacier_b08_autorift.ipynb
```

目标：

- 读取 Part 2 下载的两期 B08 GeoTIFF。
- 对两期影像进行 overlap coregistration。
- 运行 autoRIFT optical feature tracking。
- 将像素位移转换为 m/day。
- 保存静态结果图和 Streamlit 使用的 `.npz` 文件。

输入：

```text
B08_fox_2026-03-01.tif
B08_fox_2026-03-21.tif
fox_glacier_from_osm.geojson
```

输出：

```text
autorift_scatter_demeaned_2026-03-01__2026-03-21.npz
autorift_pot_quiver_demeaned_2026-03-01__2026-03-21.png
autorift_pot_speed_scatter_demeaned_2026-03-01__2026-03-21.png
autorift_pot_kde_demeaned_2026-03-01__2026-03-21.png
```

代码逻辑：

1. 读取 reference image 和 secondary image。
2. 使用 `GeogridOptical().coregister(...)` 计算两期影像重叠范围。
3. 在重叠区域构建规则 tracking grid。
4. 对两期影像做 Wallis preprocessing。
5. 运行 autoRIFT 得到像素位移。
6. 根据影像日期差，将像素位移转换为 m/day。
7. 对 `vx` 和 `vy` 分别减去 `nanmedian`，得到 demeaned velocity。
8. 保存 quiver 图、speed scatter 图、KDE 图和 `.npz` 数据。

图片占位：

```markdown
![Part 3 quiver](images/part3_quiver.png)
![Part 3 speed scatter](images/part3_speed_scatter.png)
![Part 3 KDE](images/part3_kde.png)
```

主要 feature tracking 参数：

| 参数 | 当前值 | 作用 |
|---|---:|---|
| `DEFAULT_REF` | `B08_fox_2026-03-01.tif` | reference image |
| `DEFAULT_SEC` | `B08_fox_2026-03-21.tif` | secondary image |
| `WALLIS_WIDTH` | `7` | Wallis filter 窗口大小 |
| `SEARCH_LIMIT` | `72.0` | 最大搜索距离，单位为像素 |
| `GRID_STEP` | `12` | tracking chip center 的间隔 |
| `MARGIN` | `48` | 距离影像边缘忽略的像素范围 |
| `threads` | `4` | 并行线程数 |
| `exaggerate` | `120.0` | 静态 quiver 图中箭头放大倍数 |
| `dpi` | `160` | 静态图输出分辨率 |

参数影响：

- 增大 `GRID_STEP`：点更少，运行更快，结果更稀疏。
- 减小 `GRID_STEP`：点更多，运行更慢，结果更密集。
- 增大 `MARGIN`：减少边缘误匹配，但可用区域变小。
- 增大 `SEARCH_LIMIT`：允许更大的位移，但也可能增加误匹配。
- 修改 `WALLIS_WIDTH`：改变匹配前的局部对比度增强。
- 增大 `threads`：如果 Codespaces CPU 资源足够，运行会更快。

KDE 图相关参数：

| 参数 | 当前值 | 作用 |
|---|---:|---|
| `kde_buffer_m` | `400.0` | 冰川边界外扩 buffer，用于 KDE 采样 |
| `kde_speed_xmax` | `1.5` | KDE 图 x 轴最大速度 |
| `kde_tail_frac` | `0.25` | slow/fast tail 比较时使用的比例 |
| `kde_color` | `"darkred"` | KDE 和直方图颜色 |
| `kde_bw_factor` | `2.0` | slow-tail KDE 带宽倍数 |

## 6. Part 4: Streamlit Interactive Viewer

Notebook:

```text
4. run_streamlit_viewer.ipynb
```

Streamlit app:

```text
4. autorift_speed_scatter_app.py
```

目标：

- 在 Codespaces 中启动 Streamlit viewer。
- 通过 forwarded `8501` port 打开网页交互界面。
- 交互式查看 autoRIFT `.npz` 结果。

运行流程：

1. 打开 `4. run_streamlit_viewer.ipynb`。
2. 选择 `Python (rsa-lab)` 内核。
3. 运行 dependency check cell。
4. 运行 file check cell。
5. 运行 start Streamlit cell。
6. 在 Codespaces 的 `Ports` 面板中打开 forwarded `8501`。
7. 结束后运行 stop cell。

图片占位：

```markdown
![Codespaces port 8501](images/part4_ports.png)
![Streamlit viewer](images/part4_streamlit_viewer.png)
```

Streamlit 可交互修改内容：

| 控件 | 作用 |
|---|---|
| `Upload .npz` | 上传一个 `.npz` 文件，而不是使用路径 |
| `Path to .npz` | 选择 autoRIFT 结果文件 |
| `Stretch mode` | 选择手动色标范围或 percentile 范围 |
| `Color min / max (m/day)` | 手动设置色标最小值和最大值 |
| `Color min / max (percentile)` | 用百分位数设置色标范围 |
| `Multi-stop custom ramp` | 自定义多节点色标 |
| `Built-in colormap` | 选择内置 Plotly 色标 |
| `Reverse colormap` | 反转色标 |
| `Layer` | 在 speed scatter 和 velocity quiver 之间切换 |
| `Length x demeaned (m/day)` | 调整箭头长度倍数 |
| `Plotly stem scale` | 调整 quiver stem scale |
| `Arrowhead`, `Head angle`, `Line width`, `Color` | 调整箭头样式 |
| `Max arrows` | 限制显示的箭头数量，避免页面太慢 |
| `Marker opacity` | 调整 scatter 点透明度 |
| `Marker size` | 调整 scatter 点大小 |
| `Show raster basemap under plot` | 在结果下方显示 B08 GeoTIFF 底图 |
| `Basemap opacity` | 调整底图透明度 |

Streamlit 展示 Part 3 生成的 `.npz` 结果。Feature tracking 参数在 Part 3 中修改。
