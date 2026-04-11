import math
import numpy as np
from typing import List


EARTH_RADIUS_KM = 6371.0
AVG_CAR_SPEED_KMH = 60.0


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_KM * c


def compute_distance_matrix(lats: List[float], lngs: List[float]) -> np.ndarray:
    n = len(lats)
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine(lats[i], lngs[i], lats[j], lngs[j])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def compute_travel_time_matrix(distance_matrix: np.ndarray) -> np.ndarray:
    return (distance_matrix / AVG_CAR_SPEED_KMH) * 60.0
