from pathlib import Path

import pandas as pd

from vanet_osm_warning.behavior_viz import generate_behavior_visualizations


def test_generate_behavior_replay(tmp_path: Path):
    pd.DataFrame([
        {"time_s": 0.0, "vehicle_id": "v0", "x_m": 0, "y_m": 0, "speed_mps": 10, "warning_received": False, "is_incident_vehicle": True},
        {"time_s": 0.0, "vehicle_id": "v1", "x_m": -10, "y_m": 0, "speed_mps": 10, "warning_received": False, "is_incident_vehicle": False},
        {"time_s": 1.0, "vehicle_id": "v0", "x_m": 5, "y_m": 0, "speed_mps": 0, "warning_received": False, "is_incident_vehicle": True},
        {"time_s": 1.0, "vehicle_id": "v1", "x_m": -2, "y_m": 0, "speed_mps": 4, "warning_received": True, "is_incident_vehicle": False},
    ]).to_csv(tmp_path / "trajectories_caseA.csv", index=False)
    pd.DataFrame([
        {"time_s": 0.5, "event": "v2v_packet_sent", "sender": "v0", "receiver": "v1", "protocol": "DSRC"},
        {"time_s": 0.7, "event": "warning_received", "sender": "v0", "receiver": "v1", "protocol": "DSRC"},
    ]).to_csv(tmp_path / "events_caseA.csv", index=False)

    files = generate_behavior_visualizations(tmp_path, frame_step_s=0.25)
    assert len(files) == 1
    assert files[0].exists()
    assert (tmp_path / "behavior_visualization" / "index.html").exists()
    text = files[0].read_text(encoding="utf-8")
    assert "v2v_packet_sent" in text
    assert "caseA" in text
