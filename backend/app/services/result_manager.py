import json
import os
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage")
RESULTS_DIR = os.path.join(STORAGE_DIR, "results")
MANIFESTS_DIR = os.path.join(STORAGE_DIR, "manifests")
EXPORTS_DIR = os.path.join(STORAGE_DIR, "exports")

MANIFEST_FILE = os.path.join(MANIFESTS_DIR, "results_manifest.json")


class ResultManager:
    def __init__(self):
        for d in [RESULTS_DIR, MANIFESTS_DIR, EXPORTS_DIR]:
            os.makedirs(d, exist_ok=True)
        if not os.path.exists(MANIFEST_FILE):
            self._save_manifest({"results": []})

    def _load_manifest(self) -> Dict:
        if os.path.exists(MANIFEST_FILE):
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"results": []}

    def _save_manifest(self, manifest: Dict):
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def save_result(self, result: Dict[str, Any]) -> str:
        result_id = result["result_id"]
        filename = f"{result_id}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        manifest = self._load_manifest()
        manifest["results"].append({
            "result_id": result_id,
            "file_name": filename,
            "created_at": result.get("created_at", datetime.now().isoformat()),
            "algorithm": result.get("summary", {}).get("algorithm", ""),
            "total_distance_km": result.get("summary", {}).get("total_distance_km", 0),
            "total_time_min": result.get("summary", {}).get("total_time_min", 0),
            "total_co2_kg": result.get("summary", {}).get("total_co2_kg", 0),
        })
        self._save_manifest(manifest)
        return result_id

    def get_results_list(self) -> List[Dict]:
        manifest = self._load_manifest()
        return manifest.get("results", [])

    def get_result(self, result_id: str) -> Optional[Dict]:
        filepath = os.path.join(RESULTS_DIR, f"{result_id}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def delete_result(self, result_id: str) -> bool:
        filepath = os.path.join(RESULTS_DIR, f"{result_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            manifest = self._load_manifest()
            manifest["results"] = [
                r for r in manifest["results"] if r["result_id"] != result_id
            ]
            self._save_manifest(manifest)
            return True
        return False

    def import_result(self, data: Dict[str, Any]) -> str:
        if "result_id" not in data:
            data["result_id"] = f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return self.save_result(data)

    def export_json(self, result_id: str) -> Optional[str]:
        result = self.get_result(result_id)
        if not result:
            return None
        filepath = os.path.join(EXPORTS_DIR, f"{result_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return filepath

    def export_csv(self, result_id: str) -> Optional[str]:
        result = self.get_result(result_id)
        if not result:
            return None
        filepath = os.path.join(EXPORTS_DIR, f"{result_id}.csv")
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Day", "Order", "ID", "Name", "Type", "Arrival", "Departure", "Visit_Time_Min"])
            for day in result.get("days", []):
                for place in day.get("places", []):
                    writer.writerow([
                        day["day_no"],
                        place.get("order", ""),
                        place.get("id", ""),
                        place.get("name", ""),
                        place.get("type", ""),
                        place.get("arrival", ""),
                        place.get("departure", ""),
                        place.get("visit_time_min", ""),
                    ])
            writer.writerow([])
            writer.writerow(["Summary"])
            summary = result.get("summary", {})
            writer.writerow(["Total Distance (km)", summary.get("total_distance_km", "")])
            writer.writerow(["Total Time (min)", summary.get("total_time_min", "")])
            writer.writerow(["Total CO2 (kg)", summary.get("total_co2_kg", "")])
            writer.writerow(["Hotel", summary.get("selected_hotel", "")])
            writer.writerow(["Algorithm", summary.get("algorithm", "")])
        return filepath
