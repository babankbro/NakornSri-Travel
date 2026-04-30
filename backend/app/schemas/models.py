from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class PlaceType(str, Enum):
    DEPOT = "Depot"
    HOTEL = "Hotel"
    TRAVEL = "Travel"
    CULTURE = "Culture"
    OTOP = "OTOP"
    FOOD = "Food"
    CAFE = "Café"
    FOOD_CAFE = "Food and Café"


class AlgorithmType(str, Enum):
    SM = "sm"
    SA = "sa"
    GA = "ga"
    ALNS = "alns"
    SM_ALNS = "sm_alns"
    SA_ALNS = "sa_alns"
    GA_ALNS = "ga_alns"
    MOMA = "moma"
    LINGO = "lingo"


class LifestyleType(str, Enum):
    ALL = "all"
    CULTURE = "culture"
    CAFE = "cafe"
    FOOD = "food"


class Place(BaseModel):
    order: int
    id: str
    name: str
    lat: float
    lng: float
    visit_time: int
    rate: float
    co2: float = 0.0
    type: PlaceType

    # Keywords in Thai/English that identify a Travel place containing a cafe inside
    _CAFE_TRAVEL_KEYWORDS = ("คาเฟ่", "cafe", "ฟาร์ม", "farm", "วัลเลย์", "valley")

    @property
    def is_food(self) -> bool:
        return "Food" in self.type.value

    @property
    def is_cafe(self) -> bool:
        val = self.type.value.lower()
        return "café" in val or "cafe" in val

    @property
    def is_cafe_travel(self) -> bool:
        """True when this is a Travel place that physically contains a cafe/farm cafe."""
        if self.type != PlaceType.TRAVEL:
            return False
        name_lower = self.name.lower()
        return any(kw.lower() in name_lower for kw in self._CAFE_TRAVEL_KEYWORDS)

    @property
    def is_tourist(self) -> bool:
        return self.type not in (PlaceType.DEPOT, PlaceType.HOTEL)


class OptimizeRequest(BaseModel):
    trip_days: int = Field(default=2, ge=1, le=3)
    algorithm: AlgorithmType = AlgorithmType.GA
    lifestyle_type: LifestyleType = LifestyleType.ALL
    weight_distance: float = Field(default=0.4, ge=0, le=1)
    weight_co2: float = Field(default=0.3, ge=0, le=1)
    weight_rating: float = Field(default=0.3, ge=0, le=1)
    min_places_per_day: int = Field(default=5, ge=1, le=10)
    max_places_per_day: int = Field(default=7, ge=1, le=10)
    start_place_type: str = "airport"
    end_place_type: str = "airport"


class DayRoute(BaseModel):
    day_no: int
    places: List[Dict[str, Any]]
    distance_km: float
    time_min: float
    co2_kg: float


class RouteSummary(BaseModel):
    total_distance_km: float
    total_time_min: float
    total_co2_kg: float
    average_rating: Optional[float] = 0.0
    total_rating_score: Optional[float] = 0.0
    max_rating_score: Optional[float] = 0.0
    selected_hotel: Optional[str] = None
    algorithm: str
    lifestyle_type: str


class RouteResult(BaseModel):
    result_id: str
    created_at: str
    request: Dict[str, Any]
    summary: RouteSummary
    days: List[DayRoute]
    map_data: Dict[str, Any]


class MapMarker(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    type: str
    order_in_day: Optional[int] = None
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None


class MapDay(BaseModel):
    day_no: int
    color: str
    markers: List[MapMarker]
    polyline: List[List[float]]


class CompareItem(BaseModel):
    algorithm: str
    result_id: str
    total_distance_km: float
    total_time_min: float
    total_co2_kg: float
    computation_time_sec: float
