import pandas as pd
import numpy as np
import os
from typing import Dict, List, Optional, Tuple

from backend.app.schemas.models import Place, PlaceType
from backend.app.utils.distance import (
    compute_distance_matrix,
    compute_travel_time_matrix,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
INPUTS_DIR = os.path.join(DATA_DIR, "inputs")


class DataLoader:
    def __init__(self):
        self.places: List[Place] = []
        self.places_df: Optional[pd.DataFrame] = None
        self.distance_matrix: Optional[np.ndarray] = None
        self.travel_time_matrix: Optional[np.ndarray] = None
        self.id_to_index: Dict[str, int] = {}
        self.index_to_id: Dict[int, str] = {}
        self.using_google_api: bool = False

    def load_places(self, filepath: Optional[str] = None) -> List[Place]:
        if filepath is None:
            filepath = os.path.join(DATA_DIR, "TravelInfo_v3.csv")
            if not os.path.exists(filepath):
                filepath = os.path.join(DATA_DIR, "TravelInfo_v2.csv")
            if not os.path.exists(filepath):
                filepath = os.path.join(INPUTS_DIR, "TravelInfo_v2.csv")

        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        df["CO2"] = pd.to_numeric(df["CO2"], errors="coerce").fillna(0.0)
        df["CO2"] = (df["CO2"] * 1000) / 365.0  # Convert tons/year to kg/day
        df["RATE"] = pd.to_numeric(df["RATE"], errors="coerce").fillna(0.0)
        df["VisitTime"] = pd.to_numeric(df["VisitTime"], errors="coerce").fillna(0).astype(int)

        self.places_df = df
        self.places = []
        self.id_to_index = {}
        self.index_to_id = {}

        for idx, row in df.iterrows():
            place = Place(
                order=int(row["Order"]),
                id=str(row["ID"]).strip(),
                name=str(row["Name"]).strip(),
                lat=float(row["LAT"]),
                lng=float(row["LNG"]),
                visit_time=int(row["VisitTime"]),
                rate=float(row["RATE"]),
                co2=float(row["CO2"]),
                type=PlaceType(str(row["TYPE"]).strip()),
            )
            self.places.append(place)
            self.id_to_index[place.id] = idx
            self.index_to_id[idx] = place.id

        self._compute_matrices()
        return self.places

    def _compute_matrices(self):
        if self.places_df is None:
            return
        lats = self.places_df["LAT"].tolist()
        lngs = self.places_df["LNG"].tolist()
        self.distance_matrix = compute_distance_matrix(lats, lngs)
        self.travel_time_matrix = compute_travel_time_matrix(self.distance_matrix)

    def load_matrix_from_csv(self, filepath: str, matrix_type: str) -> np.ndarray:
        df = pd.read_csv(filepath, index_col=0)
        matrix = df.values.astype(float)
        if matrix_type == "distance":
            self.distance_matrix = matrix
        elif matrix_type == "time":
            self.travel_time_matrix = matrix
        return matrix

    def load_google_matrices(self, api_key: str) -> Dict:
        """Fetch real distance and travel time from Google Distance Matrix API."""
        import urllib.request
        import json
        import re

        # ทำความสะอาด API key - ลบ whitespace, newline, control characters
        api_key = re.sub(r'[\s\r\n\t]+', '', api_key.strip())
        
        if not api_key:
            return {
                "success": False,
                "api_calls": 0,
                "matrix_size": 0,
                "errors": ["API key is empty after cleaning"],
                "using_google": False,
            }

        n = len(self.places)
        dist_mat = np.zeros((n, n))
        time_mat = np.zeros((n, n))
        
        # Incremental Load: Check existing cache
        dist_path = os.path.join(INPUTS_DIR, "google_distance_matrix.csv")
        time_path = os.path.join(INPUTS_DIR, "google_travel_time_matrix.csv")
        cached_dist = None
        cached_time = None
        if os.path.exists(dist_path) and os.path.exists(time_path):
            try:
                cached_dist = pd.read_csv(dist_path, index_col=0)
                cached_time = pd.read_csv(time_path, index_col=0)
                print(f"[DataLoader] Found existing Google cache with size {cached_dist.shape[0]}x{cached_dist.shape[1]}")
            except Exception as e:
                print(f"[DataLoader] Failed to load existing cache: {e}")
                cached_dist = None
                cached_time = None

        batch_size = 10
        total_calls = 0
        errors = []
        
        # Determine which cells need to be fetched
        needs_fetch = np.zeros((n, n), dtype=bool)
        for i, p1 in enumerate(self.places):
            for j, p2 in enumerate(self.places):
                # If cache exists and both IDs are in cache, use cached values
                if cached_dist is not None and p1.id in cached_dist.index and p2.id in cached_dist.columns:
                    dist_mat[i][j] = cached_dist.loc[p1.id, p2.id]
                    time_mat[i][j] = cached_time.loc[p1.id, p2.id]
                else:
                    needs_fetch[i][j] = True

        total_cells_to_fetch = int(np.sum(needs_fetch))
        if total_cells_to_fetch == 0:
            print("[DataLoader] All distances are already cached. No Google API calls needed.")
            self.distance_matrix = dist_mat
            self.travel_time_matrix = time_mat
            self.using_google_api = True
            self._save_google_matrices()
            return {
                "success": True,
                "api_calls": 0,
                "matrix_size": n,
                "errors": [],
                "using_google": True,
            }

        print(f"\n{'='*70}")
        print(f"[Google API] เริ่มดึงข้อมูล Distance Matrix สำหรับสถานที่ใหม่")
        print(f"[Google API] จำนวนเซลล์ที่ต้องดึง: {total_cells_to_fetch} จาก {n*n} เซลล์")
        print(f"{'='*70}\n")

        # Create batches for missing data
        coords = [f"{p.lat},{p.lng}" for p in self.places]
        batches_to_run = []
        
        for i_start in range(0, n, batch_size):
            i_end = min(i_start + batch_size, n)
            for j_start in range(0, n, batch_size):
                j_end = min(j_start + batch_size, n)
                
                # Check if this batch has any cell needing fetch
                batch_needs_fetch = needs_fetch[i_start:i_end, j_start:j_end].any()
                if batch_needs_fetch:
                    batches_to_run.append((i_start, i_end, j_start, j_end))

        total_batches = len(batches_to_run)
        print(f"[Google API] จำนวน API calls ที่คาดว่าจะใช้: {total_batches} batches")

        current_batch = 0
        for i_start, i_end, j_start, j_end in batches_to_run:
            origins = "|".join(coords[i_start:i_end])
            destinations = "|".join(coords[j_start:j_end])
            current_batch += 1

            # แสดงข้อมูล batch ปัจจุบัน
            origin_coords = [f"{p.id}({p.lat:.4f},{p.lng:.4f})" for p in self.places[i_start:i_end]]
            dest_coords = [f"{p.id}({p.lat:.4f},{p.lng:.4f})" for p in self.places[j_start:j_end]]
            
            print(f"[Batch {current_batch}/{total_batches}] Origins: {', '.join(origin_coords)}")
            print(f"                  Destinations: {', '.join(dest_coords)}")

            url = (
                f"https://maps.googleapis.com/maps/api/distancematrix/json"
                f"?origins={origins}"
                f"&destinations={destinations}"
                f"&mode=driving&units=metric&key={api_key}"
            )
            try:
                req = urllib.request.urlopen(url, timeout=10)
                response_text = req.read().decode('utf-8')
                
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as je:
                    error_msg = f"Invalid JSON response: {response_text[:100]}"
                    errors.append(error_msg)
                    print(f"  ❌ {error_msg}")
                    continue
                
                total_calls += 1

                if data.get("status") != "OK":
                    error_msg = f"API error: {data.get('status')} - {data.get('error_message', 'No details')}"
                    errors.append(error_msg)
                    print(f"  ❌ {error_msg}")
                    continue

                success_count = 0
                fallback_count = 0

                for ri, row in enumerate(data["rows"]):
                    gi = i_start + ri
                    for ci, elem in enumerate(row["elements"]):
                        gj = j_start + ci
                        
                        # Only update if it needed fetch (to avoid overwriting valid cached data if batch overlaps)
                        if needs_fetch[gi][gj]:
                            if elem.get("status") == "OK":
                                dist_mat[gi][gj] = elem["distance"]["value"] / 1000.0
                                time_mat[gi][gj] = elem["duration"]["value"] / 60.0
                                success_count += 1
                                needs_fetch[gi][gj] = False
                            else:
                                from backend.app.utils.distance import haversine
                                dist_mat[gi][gj] = haversine(
                                    self.places[gi].lat, self.places[gi].lng,
                                    self.places[gj].lat, self.places[gj].lng
                                )
                                time_mat[gi][gj] = dist_mat[gi][gj] / 60.0 * 60.0
                                fallback_count += 1
                                needs_fetch[gi][gj] = False
                
                print(f"  ✅ สำเร็จ: {success_count} คู่", end="")
                if fallback_count > 0:
                    print(f" | ⚠️  Fallback (Haversine): {fallback_count} คู่")
                else:
                    print()
                
            except Exception as e:
                error_msg = str(e)
                errors.append(error_msg)
                print(f"  ❌ Exception: {error_msg}")
            
            print()  # บรรทัดว่าง

        # Fallback for any cells that failed completely (e.g. batch failed)
        remaining_missing = int(np.sum(needs_fetch))
        if remaining_missing > 0:
            print(f"[DataLoader] ⚠️ Applying Haversine fallback to {remaining_missing} missing cells")
            from backend.app.utils.distance import haversine
            for i in range(n):
                for j in range(n):
                    if needs_fetch[i][j]:
                        dist_mat[i][j] = haversine(
                            self.places[i].lat, self.places[i].lng,
                            self.places[j].lat, self.places[j].lng
                        )
                        time_mat[i][j] = dist_mat[i][j] / 60.0 * 60.0

        # บันทึก matrices แม้มี errors บางส่วน (partial success)
        self.distance_matrix = dist_mat
        self.travel_time_matrix = time_mat
        
        if len(errors) == 0:
            self.using_google_api = True
            print(f"\n{'='*70}")
            print(f"[DataLoader] ✅ Google API สำเร็จ: {total_calls} calls, {n}x{n} matrix")
            print(f"{'='*70}\n")
            self._save_google_matrices()
        elif len(errors) < total_batches:
            # Partial success - บันทึก cache ด้วย
            self.using_google_api = True
            print(f"\n{'='*70}")
            print(f"[DataLoader] ⚠️  Google API สำเร็จบางส่วน: {total_calls - len(errors)}/{total_calls} batches")
            print(f"[DataLoader] Errors: {len(errors)} batches failed")
            print(f"{'='*70}\n")
            self._save_google_matrices()
        else:
            print(f"\n{'='*70}")
            print(f"[DataLoader] ❌ Google API ล้มเหลว: {len(errors)} errors")
            print(f"{'='*70}\n")

        return {
            "success": len(errors) == 0,
            "api_calls": total_calls,
            "matrix_size": n,
            "errors": errors,
            "using_google": self.using_google_api,
        }

    def _save_google_matrices(self):
        """Persist fetched Google matrices to CSV so they can be reused."""
        os.makedirs(INPUTS_DIR, exist_ok=True)
        ids = [p.id for p in self.places]
        dist_df = pd.DataFrame(self.distance_matrix, index=ids, columns=ids)
        time_df = pd.DataFrame(self.travel_time_matrix, index=ids, columns=ids)
        dist_path = os.path.join(INPUTS_DIR, "google_distance_matrix.csv")
        time_path = os.path.join(INPUTS_DIR, "google_travel_time_matrix.csv")
        dist_df.to_csv(dist_path)
        time_df.to_csv(time_path)
        print(f"[DataLoader] Saved Google matrices -> {dist_path}")

    def load_cached_google_matrices(self) -> bool:
        """Load previously saved Google matrices if they exist. Returns True if loaded."""
        dist_path = os.path.join(INPUTS_DIR, "google_distance_matrix.csv")
        time_path = os.path.join(INPUTS_DIR, "google_travel_time_matrix.csv")
        if os.path.exists(dist_path) and os.path.exists(time_path):
            try:
                dist_df = pd.read_csv(dist_path, index_col=0)
                time_df = pd.read_csv(time_path, index_col=0)
                
                # ตรวจสอบว่า matrix size ตรงกับจำนวน places
                if dist_df.shape[0] != len(self.places) or time_df.shape[0] != len(self.places):
                    print(f"[DataLoader] ⚠️  Cache size mismatch: matrix={dist_df.shape[0]}, places={len(self.places)}")
                    return False
                
                self.distance_matrix = dist_df.values.astype(float)
                self.travel_time_matrix = time_df.values.astype(float)
                
                # Rebuild id_to_index mapping
                self.id_to_index = {p.id: i for i, p in enumerate(self.places)}
                
                self.using_google_api = True
                print(f"[DataLoader] Loaded cached Google matrices from {INPUTS_DIR}")
                print(f"[DataLoader] Matrix size: {dist_df.shape[0]}x{dist_df.shape[1]}, Places: {len(self.places)}")
                return True
            except Exception as e:
                print(f"[DataLoader] ❌ Failed to load cached matrices: {e}")
                return False
        return False

    def google_cache_info(self) -> dict:
        """Return info about cached Google matrix files."""
        dist_path = os.path.join(INPUTS_DIR, "google_distance_matrix.csv")
        time_path = os.path.join(INPUTS_DIR, "google_travel_time_matrix.csv")
        dist_exists = os.path.exists(dist_path)
        time_exists = os.path.exists(time_path)
        mtime = None
        if dist_exists:
            import datetime
            mtime = datetime.datetime.fromtimestamp(
                os.path.getmtime(dist_path)
            ).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "cached": dist_exists and time_exists,
            "last_updated": mtime,
            "using_google": self.using_google_api,
        }

    def get_distance(self, id1: str, id2: str) -> float:
        i, j = self.id_to_index[id1], self.id_to_index[id2]
        return self.distance_matrix[i][j]

    def get_travel_time(self, id1: str, id2: str) -> float:
        i, j = self.id_to_index[id1], self.id_to_index[id2]
        return self.travel_time_matrix[i][j]

    def get_place_co2(self, place_id: str) -> float:
        """CO2 is a property of the place (from CSV), not a travel cost."""
        place = next((p for p in self.places if p.id == place_id), None)
        return place.co2 if place else 0.0

    def get_places_by_type(self, place_type: PlaceType) -> List[Place]:
        return [p for p in self.places if p.type == place_type]

    def get_depot(self) -> Place:
        depots = self.get_places_by_type(PlaceType.DEPOT)
        if depots:
            return depots[0]
        raise ValueError("No depot (airport) found in data")

    def get_hotels(self) -> List[Place]:
        return self.get_places_by_type(PlaceType.HOTEL)

    def get_tourist_places(self) -> List[Place]:
        return [p for p in self.places if p.type in (
            PlaceType.TRAVEL, PlaceType.CULTURE,
            PlaceType.OTOP, PlaceType.FOOD,
            PlaceType.CAFE, PlaceType.FOOD_CAFE,
        )]

    def get_cafe_places(self) -> List[Place]:
        return [p for p in self.places if p.type in (PlaceType.CAFE, PlaceType.FOOD_CAFE)]

    def get_otop_places(self) -> List[Place]:
        return self.get_places_by_type(PlaceType.OTOP)

    def validate(self) -> Dict:
        errors = []
        if not self.places:
            errors.append("No places loaded")
        if not self.get_places_by_type(PlaceType.DEPOT):
            errors.append("No depot (airport) found")
        if not self.get_hotels():
            errors.append("No hotels found")
        if not self.get_tourist_places():
            errors.append("No tourist places found")
        if not self.get_otop_places():
            errors.append("No OTOP places found")
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "total_records": len(self.places),
        }
