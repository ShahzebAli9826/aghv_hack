# Project Issues & Feature Tracking

## Issue #1: Dynamic Evacuation Path & Infrastructure POI Geometry in Nowcast
- **Status:** ✅ RESOLVED
- **Date Fixed:** 2026-10-19

### Problem Summary
Previously, in `dell-flood-app/src/components/NowcastPanel.tsx`, the evacuation route polyline, road hazard line, and infrastructure markers (Hospital, Transit Hub, Underpass, Shelter) were plotted using fixed relative coordinate offsets (`activeLat - 0.0125`, `activeLon - 0.0095`, etc.).

### Fix Implemented
1. **Dynamic Topographic High-Ground Destination:**
   - Implemented `compute_dynamic_evacuation_bundle` in `dell-flood-backend/app/api/endpoints.py` to analyze the 512×512 Digital Elevation Model (DEM) and find the actual highest safe ground outside the flooded basin for the designated shelter destination (`dest_lat`, `dest_lon`).
2. **Time-Varying Dijkstra Pathfinding (`DynamicEvacuationRouter`):**
   - Wired `dynamic_evacuation_route` from the backend (`endpoints.py` -> `/api/nowcast/simulate` and `/api/detect`) directly into `NowcastPanel.tsx`.
   - The safe evacuation path now dynamically draws the real calculated waypoints (`route_geometry`), bypassing submerged segments.
   - The blocked shortest path (`static_route_geometry`) highlights the actual impassable underpass/chokepoint where water exceeds 30 cm.
3. **Dynamic Infrastructure Coordinates:**
   - Generated `infrastructure_assets` with real calculated coordinates for the high-ground shelter, flooded road chokepoint, hospital, and transit corridor.
   - Wired Leaflet markers in `NowcastPanel.tsx` to render each asset at its true computed geographic coordinates (`asset.lat`, `asset.lon`).
   - Connected `handleOpenGoogleMapsShelter` to navigate directly to the true dynamic high-ground shelter coordinates.
