import urllib.request
import json
import time

API_URL = "http://localhost:8000/api/v1/routes/optimize"
RESULTS_URL = "http://localhost:8000/api/v1/results"

def run_test(lifestyle="all", w_dist=0.33, w_co2=0.33, w_rate=0.33, test_name=""):
    print(f"Running test: {test_name}...")
    body = json.dumps({
        "trip_days": 2,
        "algorithm": "ga_alns",
        "lifestyle_type": lifestyle,
        "weight_distance": w_dist,
        "weight_co2": w_co2,
        "weight_rating": w_rate,
        "min_places_per_day": 5,
        "max_places_per_day": 7
    }).encode('utf-8')
    
    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req) as response:
            resp = json.loads(response.read())
    except Exception as e:
        print(f"Error running {test_name}: {e}. (Make sure the FastAPI server is running on port 8000)")
        return None

    computation_time = resp.get("computation_time_sec", time.time() - start_time)
    
    # Fetch full result for places
    rid = resp["result_id"]
    try:
        with urllib.request.urlopen(f"{RESULTS_URL}/{rid}") as response2:
            full = json.loads(response2.read())
    except Exception as e:
        print(f"Error fetching result {rid}: {e}")
        return None
        
    places_list = []
    for day in full["days"]:
        day_places = [p["name"] for p in day["places"]]
        places_list.append(f"Day {day['day_no']}: " + " -> ".join(day_places))
        
    places_str = "<br>".join(places_list)
    distance = resp["summary"]["total_distance_km"]
    co2 = resp["summary"]["total_co2_kg"]
    
    return {
        "places": places_str,
        "distance": distance,
        "time_sec": computation_time,
        "co2": co2,
        "image": "*(รอแนบรูปภาพจากระบบ)*"
    }

def format_row(res):
    if not res:
        return "| 1 | *Error running test* | - | - | - | - |"
    return f"| 1 | {res['places']} | {res['distance']:.2f} km | {res['time_sec']:.2f} s | {res['co2']:.2f} kg | {res['image']} |"

def generate_report():
    print("Testing against running server on http://localhost:8000 ...")
    
    res_multi = run_test("all", 0.33, 0.33, 0.33, "Multi-Objective")
    res_culture = run_test("culture", 0.4, 0.3, 0.3, "Culture Lifestyle")
    res_cafe = run_test("cafe", 0.4, 0.3, 0.3, "Cafe Lifestyle")
    res_food = run_test("food", 0.4, 0.3, 0.3, "Food Lifestyle")
    res_dist = run_test("all", 0.8, 0.1, 0.1, "Distance Domain")
    res_co2 = run_test("all", 0.1, 0.8, 0.1, "CO2 Domain")
    res_rate = run_test("all", 0.1, 0.1, 0.8, "Rating Domain")
    
    md = f"""# Test Plan & Results: Travel Styles and Objectives (GA+ALNS)

## ตารางที่ 3.3 ผลจากการจัดเส้นทางที่ดีที่สุด เมื่อพิจารณา multi Objective
| เส้นทางที่ | สถานที่ | ระยะทางรวม | ระยะเวลา (s) | ปริมาณ CO2 | ภาพแต่ละเส้นทาง |
| :--- | :--- | :--- | :--- | :--- | :--- |
{format_row(res_multi)}

---

## 1.4 ผลจากการจัดเส้นทางที่ดีที่สุด เมื่อพิจารณาตามไลฟ์สไตน์

### 1.4.1 สายวัฒนธรรม
สายวัฒนธรรมมีขั้นตอนในการพิจารณา: เลือกระบุ `lifestyle_type="culture"` เพื่อเน้นการคัดเลือกสถานที่ประเภทวัฒนธรรม (Culture) เข้าสู่แผนการเดินทางเป็นลำดับแรก
| เส้นทางที่ | สถานที่ | ระยะทางรวม | ระยะเวลา (s) | ปริมาณ CO2 | ภาพแต่ละเส้นทาง |
| :--- | :--- | :--- | :--- | :--- | :--- |
{format_row(res_culture)}

### 1.4.2 สายคาเฟ่ติดแกรม
สายคาเฟ่ติดแกรมมีขั้นตอนในการพิจารณา: เลือกระบุ `lifestyle_type="cafe"` เพื่อเน้นการคัดเลือกสถานที่ประเภทท่องเที่ยว/จุดถ่ายรูป (Travel) เข้าสู่แผนการเดินทางเป็นลำดับแรก
| เส้นทางที่ | สถานที่ | ระยะทางรวม | ระยะเวลา (s) | ปริมาณ CO2 | ภาพแต่ละเส้นทาง |
| :--- | :--- | :--- | :--- | :--- | :--- |
{format_row(res_cafe)}

### 1.4.3 สายของอร่อย
สายของอร่อยมีขั้นตอนในการพิจารณา: เลือกระบุ `lifestyle_type="food"` เพื่อเน้นการคัดเลือกร้านอาหารและคาเฟ่ (Food) เข้าสู่แผนการเดินทาง
| เส้นทางที่ | สถานที่ | ระยะทางรวม | ระยะเวลา (s) | ปริมาณ CO2 | ภาพแต่ละเส้นทาง |
| :--- | :--- | :--- | :--- | :--- | :--- |
{format_row(res_food)}

---

## 1.5 ผลจากการจัดเส้นทางที่ดีที่สุด เมื่อพิจารณาตามแต่ละ Objective Domain

### 1.5.1 Distance Domain (เน้นระยะทางสั้นที่สุด)
ขั้นตอนในการพิจารณา: กำหนดค่าน้ำหนัก Objective Weights โดยเน้นระยะทาง -> **Distance=0.8, CO2=0.1, Rating=0.1**
| เส้นทางที่ | สถานที่ | ระยะทางรวม | ระยะเวลา (s) | ปริมาณ CO2 | ภาพแต่ละเส้นทาง |
| :--- | :--- | :--- | :--- | :--- | :--- |
{format_row(res_dist)}

### 1.5.2 CO2 Domain (เน้นปล่อยคาร์บอนน้อยที่สุด)
ขั้นตอนในการพิจารณา: กำหนดค่าน้ำหนัก Objective Weights โดยเน้นปริมาณคาร์บอน -> **Distance=0.1, CO2=0.8, Rating=0.1**
| เส้นทางที่ | สถานที่ | ระยะทางรวม | ระยะเวลา (s) | ปริมาณ CO2 | ภาพแต่ละเส้นทาง |
| :--- | :--- | :--- | :--- | :--- | :--- |
{format_row(res_co2)}

### 1.5.3 Rating Domain (เน้นสถานที่ยอดนิยม)
ขั้นตอนในการพิจารณา: กำหนดค่าน้ำหนัก Objective Weights โดยเน้นสถานที่ยอดนิยม -> **Distance=0.1, CO2=0.1, Rating=0.8**
| เส้นทางที่ | สถานที่ | ระยะทางรวม | ระยะเวลา (s) | ปริมาณ CO2 | ภาพแต่ละเส้นทาง |
| :--- | :--- | :--- | :--- | :--- | :--- |
{format_row(res_rate)}
"""

    with open("test_style_travel_and_each_objective.md", "w", encoding="utf-8") as f:
        f.write(md)
        
    print("Report successfully written to test_style_travel_and_each_objective.md!")

if __name__ == "__main__":
    generate_report()
