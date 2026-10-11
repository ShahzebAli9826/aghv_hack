# U-RNN Integration Blueprint for AEGIS
### Elevating Aegis from Static Satellite Delineation to 4D Spatiotemporal Flood Nowcasting & Dynamic Evacuation Routing

> **Reference Repository:** [holmescao/U-RNN (Journal of Hydrology 2025)](https://github.com/holmescao/U-RNN)  
> **Paper:** *U-RNN: High-resolution spatiotemporal nowcasting of urban flooding* (Cao et al., Journal of Hydrology, Vol 659, 2025)  
> **Target Project:** Aegis — AI-Powered Multimodal Satellite Flood Detection & Autonomous Response System  
> **Date:** October 2026

---

## 1. Executive Summary & Why This Matters

### The Fundamental Paradigm Shift
Currently, **Aegis** excels at **post-event and synoptic inundation delineation**:
1. Dual-encoder SegFormer MiT-B2 segments where water **was** when Sentinel-1 SAR / Sentinel-2 Optical satellites orbited overhead.
2. Topographic Wetness Index (TWI) models static topographic depressions.
3. Evacuation routing calculates shortest elevation-weighted paths based on **current snapshot terrain**.

However, real-world flood disasters suffer from a critical limitation highlighted in Aegis's own README:
> *"Standard satellite segmentation only tells you where surface water was when the satellite passed overhead. It cannot tell you ... which dry roads will submerge in the next 6 hours."*

**U-RNN (Journal of Hydrology 2025)** solves this exact bottleneck. U-RNN is a deep learning hydrodynamic surrogate model that delivers **2-meter / 1-minute resolution water-depth nowcasting ($>100\times$ faster than physics-based MIKE+ / SWMM solvers)** by combining:
1. **Multi-Scale U-shaped ConvGRU Encoder-Decoder** with skip connections.
2. **Dual-Branch YOLOX Prediction Head** (continuous water depth regression in meters + dry/wet classification mask).
3. **5-Channel Hydrological Input Tensor** fusing instantaneous rain, cumulative rainfall volume, high-res DEM, surface imperviousness, and stormwater drainage capacity.
4. **Sliding-Window Pre-warming (SWP)** for memory-efficient recurrent temporal tracking across multi-hour storm hydrographs.

By integrating U-RNN's core innovations into Aegis, we transition Aegis from a **reactive 2D flood viewer** into a **predictive 4D hydrological command center** that forecasts water depths $H(x, y, t)$ across $+15, +30, +60, +180$ minutes, enabling **Time-Varying Predictive Evacuation Routing**.

---

## 2. Deep Dive: What Can We Pull from `holmescao/U-RNN`?

Below is a breakdown of the mathematical architectures, features, and engineering paradigms extracted from the U-RNN codebase and how they map to Aegis.

```
                    ┌────────────────────────────────────────────────────────┐
                    │               U-RNN INPUT TENSOR FUSION                │
                    │  (Dynamic Rain + Cumulative Rain + DEM + Imp + Drain)  │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
                         ┌──────────────────────────────────────────────┐
                         │       3-Stage Multi-Scale ConvGRU U-Net      │
                         │   Encoder (1x, 1/2x, 1/4x) + Skip-ConvGRUs   │
                         └──────────────────────┬───────────────────────┘
                                                │
                         ┌──────────────────────┴──────────────────────┐
                         ▼                                             ▼
             [Branch 1: Wet/Dry Extent]                    [Branch 2: Water Depth mm]
             Sigmoid Classification Mask                   Leaky-ReLU Depth Map (H(x,y,t))
                         │                                             │
                         └──────────────────────┬──────────────────────┘
                                                ▼
                               ┌─────────────────────────────────┐
                               │   Thresholded Water-Depth Field │
                               │     (Zeroed-out on dry cells)   │
                               └────────────────┬────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
  [4D Time-Slider Map (Frontend)]                             [Time-Varying Dijkstra Router]
  Depth Heatmaps at t+15m, 30m, 60m                           Edge Penalty: Cost(e, t_arrival)
```

### Feature 1: Continuous Water-Depth Nowcasting vs. Binary Segmentation Masks
* **Today in Aegis:** SegFormer outputs binary/probabilistic flood masks (water vs dry ground). It cannot differentiate between **3 cm of street puddling** (completely passable by car) and **80 cm of raging torrent** (submerges vehicles, sweeps away evacuees).
* **Pulled from U-RNN:** The **Dual-Branch YOLOX Prediction Head**:
  - **Branch A (Regression):** Predicts precise continuous flood water depth $h \ge 0$ in millimeters/meters.
  - **Branch B (Classification):** Predicts wet/dry probability $\hat{p} \in [0, 1]$.
  - **Inference Masking:** Cell depth is corrected via $\tilde{h} = h \cdot \mathbb{I}(\hat{p} \ge \tau_{\text{wet}})$, completely eliminating spurious trace moisture artifacts in elevated dry terrain.

### Feature 2: 5-Factor Hydrological Input Feature Tensor
In `src/lib/dataset/Dynamic2DFlood.py`, U-RNN demonstrates how physical hydrologic dynamics can be encoded into a clean spatial-temporal tensor $(B, 1, C, H, W)$ where $C = 2W + 3$:
1. **$W$ Historical Instantaneous Rainfall Fields ($R_{t-W \dots t}$ in mm/min):** Captures storm flash intensity and cloudburst peaks.
2. **$W$ Cumulative Rainfall Fields ($\sum_{0}^t R$ in mm):** Captures total water volume poured into the catchment; cumulative volume drives ponding depths far better than instantaneous rain rate alone.
3. **Absolute DEM ($Z(x, y)$ in m):** Normalised per-sample by spatial min/max to preserve micro-topographic gravity gradients.
4. **Impervious Surface Fraction ($\phi \in [0, 1]$):** Sourced from building footprints and pavement layers. Direct proxy for the runoff coefficient ($C_{\text{runoff}} \approx 0.9$ on asphalt vs $0.15$ on vegetative soil).
5. **Drainage Infrastructure / Manhole Capacity Mask ($M \in \{0, 1\}$):** Points of subsurface stormwater discharge that alleviate surface ponding.

### Feature 3: Sliding-Window Pre-warming (SWP) Execution Engine
* **The Problem:** Recurrent neural networks (RNNs/GRUs) unrolled over 6-hour storms ($T=360$ minutes) encounter out-of-memory (OOM) errors during inference or training.
* **U-RNN Solution:** SWP divides the event timeline into overlapping sliding windows (e.g., window size $L=30$). It runs a *stateless pre-warming phase* without computing gradients up to time $t_{\text{now}}$, populating the internal hidden states $H_{\text{enc}}^{(1, 2, 3)}$ and $H_{\text{dec}}^{(1, 2, 3)}$. It then predicts the subsequent forward nowcast horizon $t + \Delta t$ seamlessly.

### Feature 4: Time-Dependent Dynamic Evacuation Routing
* **Today in Aegis:** `dell-flood-backend/app/aegis/routing/graph_router.py` computes Dijkstra path weights using static DEM elevation penalty:
  $$\text{weight} = \text{distance} \times \left(1 + \frac{\text{elev\_penalty}}{\max(\text{elev}, 0.1)}\right)$$
  This is a **static** routing graph. If a low-lying road is dry at minute 0, Aegis routes evacuees onto it. If that road submerges 20 minutes later while evacuees are in transit, they get trapped.
* **Pulled from U-RNN:** **Dynamic Spatiotemporal Edge Penalties**:
  Each road segment $e = (u, v)$ with estimated arrival time $t_{\text{arrival}} = t_0 + \frac{\text{dist}(u)}{v_{\text{evac}}}$ evaluates its cost against the **U-RNN forecasted water depth at that future timestamp**:
  $$\text{Cost}(e, t_{\text{arrival}}) = \text{length}(e) \times \left(1 + \alpha \cdot \text{Depth}\left(\text{midpoint}(e), t_{\text{arrival}}\right)^\beta\right)$$
  If $\text{Depth}(e, t_{\text{arrival}}) > 0.3\,\text{m}$ (critical vehicle stalling threshold), the edge is assigned $\text{Cost} = \infty$ (road closed in flight).

### Feature 5: Dual FocalBCE + Weighted MSE (WMSE) Objective
* Standard MSE treats a 10 cm error in dry land the same as a 10 cm error in deep water.
* U-RNN’s loss combines:
  $$\mathcal{L} = \mathcal{L}_{\text{FocalBCE}}(\hat{p}, p_{\text{binary}}) + \lambda \cdot \mathcal{L}_{\text{WMSE}}(\hat{h}, h)$$
  where $\mathcal{L}_{\text{WMSE}}$ weights errors quadratically higher in deeper inundated basins, prioritizing civilian safety in life-critical high-water zones.

---

## 3. Comparative Architecture: Aegis Current vs. Aegis + U-RNN

| Capability | Current Aegis (SegFormer + TWI) | Upgraded Aegis (with U-RNN Core) |
|---|---|---|
| **Primary Output** | Binary inundation footprint + probability score | Continuous 4D water-depth grid $H(x, y, t)$ in meters |
| **Temporal Horizon** | Static historical snapshot (when satellite passed) | Nowcasting $+15, +30, +60, +120$ minutes into the future |
| **Physics Grounding** | Topographic Wetness Index (static slope proxy) | High-speed surrogate 2D shallow-water hydrodynamics |
| **Rainfall Coupling** | 5-day accumulated scalar sum via OpenWeather | Dynamic instantaneous + cumulative rainfall sequence $(T, H, W)$ |
| **Surface Factors** | DEM elevation points from Mireye | DEM + Imperviousness fraction + Drainage inlet density |
| **Evacuation Routing** | Static elevation Dijkstra (penalizes low ground) | Dynamic Time-Varying Dijkstra (penalizes future flood arrival) |
| **Passability Triage** | Guesses road status by static elevation | Exact vehicle vs pedestrian wading clearance thresholds |
| **Inference Latency** | ~2–4 seconds (SegFormer encoder) | ~40–80 milliseconds ($>100\times$ faster than MIKE+ solvers) |

---

## 4. Architectural Integration Blueprint in Aegis Codebase

Here is the exact file-by-file mapping of where and how U-RNN components plug into Aegis:

```
Aegis/
├── dell-flood-backend/
│   ├── app/
│   │   ├── ml/
│   │   │   ├── inference.py                 # Existing SegFormer satellite model
│   │   │   └── urnn_nowcaster.py            # [NEW] U-RNN ConvGRU Nowcasting Engine
│   │   ├── aegis/
│   │   │   ├── pipeline/
│   │   │   │   ├── predictive_twi.py        # Static TWI module
│   │   │   │   └── dynamic_hydro_tensor.py  # [NEW] Prepares 5-channel physical input tensor
│   │   │   └── routing/
│   │   │       ├── graph_router.py          # Existing NetworkX Dijkstra
│   │   │       └── dynamic_router.py        # [NEW] Time-Varying Dijkstra routing on U-RNN depth
│   │   ├── agent/
│   │   │   ├── flood_agent.py               # Integrated with new NOWCAST cycle step
│   │   │   └── tools.py                     # Rainfall temporal sequence generator
│   │   └── api/
│   │       └── endpoints.py                 # Exposes /api/nowcast and dynamic routing endpoints
└── dell-flood-app/
    └── src/
        └── components/
            ├── MapView.tsx                  # Adds 60-min nowcast time-scrubber slider
            └── TriagePanel.tsx              # Shows depth-based road passability gauges
```

### Detailed Component Specifications

#### A. Component 1: `dynamic_hydro_tensor.py` (Feature Assembler)
* **Location:** `dell-flood-backend/app/aegis/pipeline/dynamic_hydro_tensor.py`
* **Duty:** Generates the normalized input tensor $(1, C, H, W)$ for any US/India target bounding box:
  - **DEM Channel:** Pulls DEM raster from Mireye physical API / USGS 3DEP (or synthetic fallback grid) and normalizes:
    $$Z_{\text{norm}} = \frac{Z - Z_{\min}}{Z_{\max} - Z_{\min} + 1\times 10^{-6}}$$
  - **Imperviousness Channel:** Uses Mireye Overture building footprints + road density to compute built-up percentage per grid cell $[0, 1]$.
  - **Drainage Channel:** Simulates municipal drainage inlet distribution based on urban road intersections.
  - **Rainfall Sequence:** Expands OpenWeather / Open-Meteo 1-hour forecasts into minute-level Hyetographs (using synthetic Huff or Chicago storm distributions) with both instantaneous rate and running cumulative sum.

#### B. Component 2: `urnn_nowcaster.py` (Inference Module)
* **Location:** `dell-flood-backend/app/ml/urnn_nowcaster.py`
* **Duty:** Implements the lightweight PyTorch/ONNX ConvGRU U-Net model:
  - Loads pre-trained weights (`lite.yaml` 128×128 or full-res checkpoint from U-RNN HuggingFace / Google Drive mirror).
  - Takes $(1, 1, C, H, W)$ tensor.
  - Propagates ConvGRU cell state across $T=15, 30, 45, 60$ minutes.
  - Returns a 4D output tensor: `water_depths[time_step, lat_idx, lon_idx]` in meters.
  - Includes a zero-GPU CPU fallback mode using a vectorized diffusion-wave hydraulic proxy so it runs deterministically in any testing environment.

#### C. Component 3: `dynamic_router.py` (Time-Dependent Pathfinding)
* **Location:** `dell-flood-backend/app/aegis/routing/dynamic_router.py`
* **Duty:** Upgrades `get_graph_route()` into time-aware route computation:
  - Calculates vehicle traveling speed ($v \approx 30\,\text{km/h}$ normal, slows to $10\,\text{km/h}$ in shallow water $< 0.15\,\text{m}$).
  - As Dijkstra explores neighbor edges $(u, v)$, it queries `urnn_nowcaster.get_depth(lat, lon, t_arrival)`.
  - If forecasted depth exceeds vehicle threshold ($0.30\,\text{m}$ for cars, $0.50\,\text{m}$ for high-clearance rescue trucks), edge is marked `IMPASSABLE`.
  - Re-routes civilians along ridges and elevated bypasses before the flash water wavefront arrives.

#### D. Component 4: SITREP LLM Prompt Grounding with Real Water Depths
* **Location:** `dell-flood-backend/app/RAG/generator.py`
* **Duty:** Enhances Bedrock / Gemini prompt with critical depth telemetry:
  ```text
  U-RNN HYDRODYNAMIC NOWCAST TELEMETRY (NEXT 60 MINUTES):
  - Peak Inundation Time: +35 minutes from present
  - Maximum Predicted Water Depth: 0.84 meters (Critical Submersion)
  - Impassable Road Corridors: Arterial Bypass NH-715 (Submerged under 0.62m at T+20min)
  - High-Ground Safe Havens Remaining Dry (<0.02m): Jorhat Stadium Shelter
  ```
  Judges and emergency directors receive specific, lifesaving guidance rather than generic advice.

#### E. Component 5: Front-End Interactive 60-Minute Timeline Scrubber
* **Location:** `dell-flood-app/src/components/MapView.tsx`
* **Duty:** Adds an interactive slider: `[ Now (0m) | +15m | +30m | +45m | +60m ]`.
  - Dragging the slider dynamically re-colors the inundation overlay:
    - Blue-cyan: $< 0.15\,\text{m}$ (Pedestrian wading)
    - Orange: $0.15 - 0.40\,\text{m}$ (Passenger cars stalled)
    - Crimson-red: $> 0.40\,\text{m}$ (Extreme danger, swift currents)
  - Displays dynamic evacuation corridors that morph in real-time as routes become compromised.

---

## 5. Mathematical & Algorithmic Formulation

### 1. ConvGRU Temporal Update
For spatial feature map $X_t$ and previous hidden state $H_{t-1}$ at encoder/decoder level $l$:

$$Z_t = \sigma(W_{xz} * X_t + W_{hz} * H_{t-1} + b_z)$$

$$R_t = \sigma(W_{xr} * X_t + W_{hr} * H_{t-1} + b_r)$$

$$\tilde{H}_t = \tanh(W_{xh} * X_t + W_{hh} * (R_t \odot H_{t-1}) + b_h)$$

$$H_t = (1 - Z_t) \odot H_{t-1} + Z_t \odot \tilde{H}_t$$

*where $*$ denotes 2D spatial convolution and $\sigma$ is the sigmoid gating function.*

### 2. Dual YOLOX Prediction Head
The final decoder output $H_t^{\text{dec}}$ branches into:

$$\hat{h}(x, y, t) = \text{LeakyReLU}\left(\text{Conv}_{1\times 1}(F_{\text{reg}}(H_t^{\text{dec}}))\right) \quad \text{[Water Depth in mm]}$$

$$\hat{p}(x, y, t) = \sigma\left(\text{Conv}_{1\times 1}(F_{\text{cls}}(H_t^{\text{dec}}))\right) \quad \text{[Wet/Dry Probability]}$$

The final physically-corrected inundation depth field is:

$$H_{\text{corrected}}(x, y, t) = \begin{cases} \hat{h}(x, y, t) / 1000.0 & \text{if } \hat{p}(x, y, t) \ge 0.5 \\ 0.0 & \text{otherwise} \end{cases}$$

### 3. Dynamic Cost Metric for Road Networks
Let edge $e = (u, v)$ have physical length $L_e$, speed limit $v_0$, and elevation $Z_e$. Given arrival time $t_a = t_{\text{start}} + \sum_{e' \in \text{path}} \tau(e')$:

$$\text{Depth}_e(t_a) = H_{\text{corrected}}\left(\text{midpoint}(e), t_a\right)$$

$$\tau(e) = \frac{L_e}{v_0 \cdot \max\left(0.1, 1.0 - \frac{\text{Depth}_e(t_a)}{0.30}\right)}$$

$$\text{Weight}(e, t_a) = \begin{cases} \infty & \text{if } \text{Depth}_e(t_a) \ge 0.30\,\text{m} \\ L_e \cdot \left(1.0 + 5.0 \cdot \left(\frac{\text{Depth}_e(t_a)}{0.30}\right)^2\right) & \text{if } \text{Depth}_e(t_a) < 0.30\,\text{m} \end{cases}$$

---

## 6. Implementation Plan & Execution Roadmap

Given the hackathon timeframe, here is the phased implementation path:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PHASED IMPLEMENTATION TIMELINE                        │
├───────────────────┬─────────────────────────────────────────────────────────┤
│ Hour 0 – 3        │ Phase 1: Feature Extraction & Hydro Tensor Builder      │
│ (Core Hydrology)  │ • Create dynamic_hydro_tensor.py                        │
│                   │ • Combine DEM + Cumulative Rainfall + Imperviousness    │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Hour 3 – 7        │ Phase 2: Lightweight U-RNN Engine & Checkpoint Setup    │
│ (ML & Nowcasting) │ • Implement urnn_nowcaster.py with PyTorch ConvGRU      │
│                   │ • Download lightweight weights (or surrogate engine)    │
│                   │ • Verify 15m/30m/60m depth output consistency          │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Hour 7 – 11       │ Phase 3: Time-Varying Evacuation Engine & Agent Binding │
│ (Routing & Agent) │ • Upgrade graph_router.py with time-aware edge costs    │
│                   │ • Integrate Nowcast into flood_agent.py Step 5b         │
│                   │ • Ground RAG situation reports with peak water depths   │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Hour 11 – 15      │ Phase 4: Frontend Time-Slider UI & Passability HUD      │
│ (User Interface)  │ • Add 0–60 min time-slider in MapView.tsx               │
│                   │ • Render depth-coded color scales (Blue/Orange/Red)     │
│                   │ • Display road passability status cards in TriagePanel  │
├───────────────────┼─────────────────────────────────────────────────────────┤
│ Hour 15 – 18      │ Phase 5: Testing, Cloud Deployment & Judge Polish       │
│ (Demo Readiness)  │ • Test full end-to-end flow with Assam & US benchmarks  │
│                   │ • Package container for AWS App Runner                  │
│                   │ • Rehearse winning 60-second pitch                      │
└───────────────────┴─────────────────────────────────────────────────────────┘
```

### Step-by-Step Action Items

#### Step 1: Create `dell-flood-backend/app/aegis/pipeline/dynamic_hydro_tensor.py`
* Build the input normalizer adhering to U-RNN's `preprocess_inputs`.
* Accept `(lat, lon, radius_km, duration_min)`.
* Fetch instantaneous rainfall rate and compute cumulative volume:
  ```python
  cum_rain = np.cumsum(rain_series)
  rain_norm = rain_series / 100.0  # max rain normalization
  cum_norm = cum_rain / max(1.0, cum_rain.max())
  ```
* Assemble normalized DEM and imperviousness arrays.

#### Step 2: Implement `dell-flood-backend/app/ml/urnn_nowcaster.py`
* Construct the 3-scale `ConvGRU` encoder and decoder architecture matching `holmescao/U-RNN/code/src/lib/model/networks/model.py`.
* Provide an automated fallback:
  - If GPU/weights are loaded: runs full ConvGRU forward pass in < 60ms.
  - If offline/CPU sandbox: executes a vectorized Cellular-Automata Manning diffusion equation using DEM slope and cumulative rain, guaranteeing identical output schemas without dependencies.

#### Step 3: Implement Dynamic Time-Dependent Evacuation in `evacuation_engine.py`
* Calculate arrival times along graph vertices.
* Reject paths that cross future submerged zones ($> 0.3\,\text{m}$ at time of vehicle arrival).
* Return comparison metrics:
  - Static Route: Distance, Submersion Risk (% probability of encountering water).
  - Dynamic U-RNN Route: Distance (+detour), Submersion Risk (0.0% guaranteed dry corridor).

#### Step 4: Wire into FastAPI (`app/api/endpoints.py`)
Add endpoint:
```python
@router.get("/nowcast")
def get_flood_nowcast(lat: float, lon: float, horizon_minutes: int = 60):
    """
    Returns spatiotemporal flood depth predictions at 15-minute intervals.
    """
```

#### Step 5: Frontend UI Enhancement
* In `MapView.tsx`, add a dynamic scrubber bar beneath the map.
* Toggle layer visibility between **Current Satellite Observation (SegFormer)** and **Future Water-Depth Forecast (U-RNN)**.

---

## 7. Hackathon Judge Pitch & Winning Talking Points

When presenting to hackathon judges in the Heat & Water track, use this narrative:

### 1. The 60-Second Pitch
> "Most flood response apps show you a static flat map of where water was hours ago when a satellite passed overhead. But flood disasters are dynamic: rain keeps falling, water drains into low basins, and roads that are dry right now will be underwater in thirty minutes.
> 
> We integrated the cutting-edge **U-RNN spatiotemporal nowcasting framework** published in the *Journal of Hydrology 2025*. By fusing satellite observation with multi-scale ConvGRU neural networks, cumulative rainfall volume, and sub-meter terrain elevation, Aegis nowcasts exact flood water depths through time at 2-meter resolution — over 100 times faster than physics-based hydrodynamic simulators.
> 
> This enables our breakthrough feature: **Time-Varying Evacuation Routing**. Aegis doesn’t just route evacuees away from current water; it computes the evacuee's speed and ensures the corridors they are traveling on won't submerge while they are on them. That is the difference between saving lives and routing civilians directly into trapped flood basins."

### 2. Key Technical Talking Points for Judges
1. **"We moved from binary classification to continuous hydrodynamic depth modeling."**  
   SegFormer gives us a 2D wet/dry mask; U-RNN gives us continuous water depth in millimeters. We know whether a road has 5cm of water (safe for emergency vehicles) or 60cm (stalls cars and sweeps away people).
2. **"Surrogate deep learning runs 100x faster than traditional MIKE+/SWMM simulators."**  
   Solving shallow-water Navier-Stokes equations across a city takes hours on cluster nodes. U-RNN evaluates the entire catchment in 60 milliseconds on consumer hardware, enabling real-time civilian routing on mobile devices.
3. **"Sliding-Window Pre-warming handles long-duration multi-hour monsoons without GPU memory exhaustion."**  
   We maintain recurrent hidden states across sliding storm windows, preserving hydrological memory from the first drop of rain without exploding memory.
4. **"Cumulative rainfall volume is the hidden driver of urban flooding."**  
   Most systems only look at rain rate (mm/hr). U-RNN proves that cumulative volume $\sum R(t)$ dictates soil saturation and stormwater drainage choking. We encode both instantaneous and cumulative tensors.
5. **"Time-dependent pathfinding prevents in-transit drownings."**  
   Standard Dijkstra is blind to the future. Our dynamic Dijkstra router calculates future water depth at the exact estimated minute of vehicle arrival.

---

## 8. Summary Checklist for Implementation

- [ ] **Read and inspect U-RNN architecture:** `Dynamic2DFlood.py`, `model.py`, `lite.yaml`.
- [ ] **Create feature tensor builder:** `dell-flood-backend/app/aegis/pipeline/dynamic_hydro_tensor.py`.
- [ ] **Create ConvGRU nowcasting inference module:** `dell-flood-backend/app/ml/urnn_nowcaster.py`.
- [ ] **Upgrade evacuation pathfinder:** Integrate dynamic time-varying edge penalties in `graph_router.py`.
- [ ] **Bind nowcast step into agent:** Hook into `flood_agent.py` cycle and RAG prompt generator.
- [ ] **Expose `/api/nowcast` endpoint:** Return 15m/30m/45m/60m geo-depth rasters.
- [ ] **Add UI timeline scrubber:** Enable user to drag time slider in `MapView.tsx`.
- [ ] **Deploy on AWS App Runner / S3:** Ensure weights and tensor processing run smoothly in the cloud.

---
*Created for Team Aegis — AI Flood Detection & Disaster Response System*
