# Export OpenStreetMap input

## Method 1: Manual export from OpenStreetMap

1. Open OpenStreetMap in a browser.
2. Zoom to a small area, for example one road segment or one district block.
3. Click **Export**.
4. Download the `.osm` file.
5. Save it as:

```bash
data/osm/my_area.osm.xml
```

Then run:

```bash
./run_vanet_osm_ubuntu.sh install-sumo
./run_vanet_osm_ubuntu.sh osm-file data/osm/my_area.osm.xml
```

## Method 2: Bounding box download

Format:

```bash
./run_vanet_osm_ubuntu.sh bbox south,west,north,east
```

Example small area in Ho Chi Minh City:

```bash
./run_vanet_osm_ubuntu.sh bbox 10.755,106.665,10.765,106.680
```

Keep the bounding box small. A very large OSM map creates too many edges and makes the SUMO conversion slow.
