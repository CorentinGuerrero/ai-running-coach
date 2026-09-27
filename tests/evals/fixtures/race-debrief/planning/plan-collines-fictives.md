# Plan de course — Trail des Collines Fictives

```arc
{
  "arc": 1, "kind": "race_plan", "date": "2024-06-01", "race_name": "Trail des Collines Fictives",
  "race_date": "2024-06-08", "distance_m": 4000, "elevation_gain_m": 0,
  "start_time": "2024-06-08T07:00:00+02:00", "target_time_s": 1200,
  "scenarios": {"ambitious": 1100, "realistic": 1200, "safe": 1320},
  "segments": [
    {"id": "s01", "km_start": 0.0, "km_end": 1.0, "distance_m": 1000.0, "grade_mean_pct": 0.0,
     "elevation_gain_m": 0.0, "elevation_loss_m": 0.0, "source": "personal",
     "predicted_time_s": {"safe": 330, "realistic": 300, "ambitious": 275},
     "pace_s_km": {"safe": 330, "realistic": 300, "ambitious": 275}, "notes": []},
    {"id": "s02", "km_start": 1.0, "km_end": 2.0, "distance_m": 1000.0, "grade_mean_pct": 0.0,
     "elevation_gain_m": 0.0, "elevation_loss_m": 0.0, "source": "personal",
     "predicted_time_s": {"safe": 330, "realistic": 300, "ambitious": 275},
     "pace_s_km": {"safe": 330, "realistic": 300, "ambitious": 275}, "notes": []},
    {"id": "s03", "km_start": 2.0, "km_end": 3.0, "distance_m": 1000.0, "grade_mean_pct": 0.0,
     "elevation_gain_m": 0.0, "elevation_loss_m": 0.0, "source": "personal",
     "predicted_time_s": {"safe": 330, "realistic": 300, "ambitious": 275},
     "pace_s_km": {"safe": 330, "realistic": 300, "ambitious": 275}, "notes": []},
    {"id": "s04", "km_start": 3.0, "km_end": 4.0, "distance_m": 1000.0, "grade_mean_pct": 0.0,
     "elevation_gain_m": 0.0, "elevation_loss_m": 0.0, "source": "personal",
     "predicted_time_s": {"safe": 330, "realistic": 300, "ambitious": 275},
     "pace_s_km": {"safe": 330, "realistic": 300, "ambitious": 275}, "notes": []}
  ]
}
```

Parcours plat fictif (zone conventionnelle du dépôt), 4 km, allure réaliste 300 s/km
(5:00/km) constante sur les quatre segments (s01-s04) — plan construit par
`scripts/arc_race_pacing.py` à partir d'un historique personnel plat.
