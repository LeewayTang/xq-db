import pytest

from xqdb.config import load_config
from xqdb.index.fts import rebuild_fts
from xqdb.store.db import connect, init_db
from xqdb.tools.context import ToolContext


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("", encoding="utf-8")
    cfg = load_config(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.db_path)
    init_db(conn)
    conn.execute(
        "insert into source(id,name,url,license,trust) "
        "values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w:z','春秋左传')")
    conn.execute(
        "insert into edition(id,work_id,source_id,char_count,quality_grade) "
        "values('e:z','w:z','s',10,'A')")
    conn.execute(
        "insert into section(id,edition_id,idx,title,level) "
        "values('s:z:1','e:z',1,'隐公元年',1)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:001','s:z:1',1,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.commit()
    rebuild_fts(conn)
    yield ToolContext(cfg=cfg, conn=conn)
    conn.close()
