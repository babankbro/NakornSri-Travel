import urllib.request
import json

def test_optimize(algorithm="ga"):
    body = json.dumps({
        "trip_days": 2,
        "algorithm": algorithm,
        "lifestyle_type": "all",
        "weight_distance": 0.4,
        "weight_time": 0.3,
        "weight_co2": 0.3,
        "max_places_per_day": 6
    }).encode()
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/routes/optimize",
        data=body, method="POST"
    )
    req.add_header("Content-Type", "application/json")
    r = urllib.request.urlopen(req)
    resp = json.loads(r.read())
    print(f"\n=== {algorithm.upper()} ===")
    print("Summary:", resp["summary"])

    # Fetch full result to check OTOP
    rid = resp["result_id"]
    r2 = urllib.request.urlopen(f"http://localhost:8000/api/v1/results/{rid}")
    full = json.loads(r2.read())
    for day in full["days"]:
        places = day["places"]
        otop_ids = [p["id"] for p in places if p["type"] == "OTOP"]
        co2_sum = sum(p.get("co2", 0) for p in places)
        print(f"  Day {day['day_no']}: {[p['id'] for p in places]}")
        print(f"    OTOP in day: {otop_ids}  (should be exactly 1)")
        print(f"    CO2 sum from places: {co2_sum:.3f}  reported: {day['co2_kg']:.3f}")

test_optimize("sm")
test_optimize("ga")
test_optimize("sa")
test_optimize("sm_alns")
