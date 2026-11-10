from xqdb.annotate.chunk import Chunk
from xqdb.annotate.events import persist_events, persist_places, persist_tags


def _chunk():
    return Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)


def test_event_time_and_participants(ctx):
    assert persist_events(ctx.conn, _chunk(), {"events": [{
        "name": "郑伯克段于鄢", "passage_id": "p:z:1:001",
        "date_text": "隐公元年", "year_start": -722, "year_end": -722,
        "confidence": "medium", "basis": "王年表", "place_name": "鄢",
        "participants": ["郑庄公", "共叔段"]}]}) == 1
    assert ctx.conn.execute("select count(*) from event").fetchone()[0] == 1
    assert ctx.conn.execute("select count(*) from passage_time").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from event_participant").fetchone()[0] == 2
    assert ctx.conn.execute(
        "select passage_id from event").fetchone()[0] == "p:z:1:001"
    assert ctx.conn.execute(
        "select count(*) from event_place").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from passage_place").fetchone()[0] == 0


def test_place_with_coordinates(ctx):
    assert persist_places(ctx.conn, _chunk(), {"places": [{
        "passage_id": "p:z:1:001", "name": "鄢", "role": "battle",
        "modern_name": "河南鄢陵", "lat": 34.1, "lon": 114.2,
        "confidence": 0.6}]}) == 1
    assert ctx.conn.execute("select count(*) from place").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from place_location").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from passage_place").fetchone()[0] == 1


def test_tags_are_upserted(ctx):
    assert persist_tags(ctx.conn, _chunk(), {"tags": [{
        "passage_id": "p:z:1:001", "name": "兄弟相残",
        "category": "母题", "confidence": 0.9}]}) == 1
    assert ctx.conn.execute("select count(*) from tag").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from passage_tag").fetchone()[0] == 1


def test_homophone_places_do_not_collide(ctx):
    persist_places(ctx.conn, _chunk(), {"places": [
        {"passage_id": "p:z:1:001", "name": "鄢"},
        {"passage_id": "p:z:1:001", "name": "燕"}]})
    rows = ctx.conn.execute("select canonical_name from place").fetchall()
    assert {row[0] for row in rows} == {"鄢", "燕"}
