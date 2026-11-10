from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class PlaceMatch:
    place_id: str
    canonical_name: str
    matched_name: str
    name_type: str
    lat: float | None
    lon: float | None
    precision_m: int | None
    modern_name: str | None
    confidence: float


def upsert_place(conn, place_id: str, canonical_name: str,
                 type: str | None = None) -> None:
    conn.execute(
        "insert into place(id, canonical_name, type) values (?, ?, ?) "
        "on conflict(id) do update set "
        "canonical_name = excluded.canonical_name, "
        "type = coalesce(excluded.type, place.type)",
        (place_id, canonical_name, type),
    )
    conn.execute(
        "insert into place_name(place_id, name, name_type, is_preferred) "
        "select ?, ?, 'canonical', 1 "
        "where not exists ("
        "  select 1 from place_name where place_id = ? and name = ?)",
        (place_id, canonical_name, place_id, canonical_name),
    )


def add_name(conn, place_id: str, name: str, name_type: str, *,
             period: str | None = None, is_preferred: bool = False) -> None:
    conn.execute(
        "insert into place_name(place_id, name, name_type, period, is_preferred) "
        "values (?, ?, ?, ?, ?)",
        (place_id, name, name_type, period, int(is_preferred)),
    )


def add_location(conn, place_id: str, lat: float, lon: float, *,
                 precision_m: int = 5000,
                 modern_province: str | None = None,
                 modern_city: str | None = None,
                 modern_county: str | None = None,
                 hypothesis: str | None = None,
                 confidence: float = 0.5,
                 is_primary: bool = False) -> None:
    conn.execute(
        "insert into place_location"
        "(place_id, lat, lon, precision_m, modern_province, modern_city,"
        " modern_county, hypothesis, confidence, is_primary) "
        "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (place_id, lat, lon, precision_m, modern_province, modern_city,
         modern_county, hypothesis, confidence, int(is_primary)),
    )


def resolve_place(conn, name: str) -> list[PlaceMatch]:
    rows = conn.execute(
        """
        select p.id as place_id, p.canonical_name,
               (select n2.name from place_name n2
                where n2.place_id = p.id and n2.name = ?
                order by n2.is_preferred desc, n2.id limit 1) as matched_name,
               (select n3.name_type from place_name n3
                where n3.place_id = p.id and n3.name = ?
                order by n3.is_preferred desc, n3.id limit 1) as name_type,
               l.lat, l.lon, l.precision_m,
               nullif(trim(coalesce(l.modern_province, '')
                    || coalesce(l.modern_city, '')
                    || coalesce(l.modern_county, '')), '') as modern_name,
               l.confidence
        from place p
        left join place_location l on l.place_id = p.id
        where p.id in (select place_id from place_name where name = ?)
        order by l.is_primary desc, l.confidence desc
        """,
        (name, name, name),
    ).fetchall()
    return [
        PlaceMatch(
            place_id=row["place_id"],
            canonical_name=row["canonical_name"],
            matched_name=row["matched_name"],
            name_type=row["name_type"],
            lat=row["lat"],
            lon=row["lon"],
            precision_m=row["precision_m"],
            modern_name=row["modern_name"],
            confidence=float(row["confidence"] or 0.0),
        )
        for row in rows
    ]


def haversine_km(a_lat: float, a_lon: float,
                 b_lat: float, b_lon: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (a_lat, a_lon, b_lat, b_lon))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))
