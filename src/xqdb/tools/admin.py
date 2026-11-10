from ..ingest.daizhige import enumerate_corpus, fetch_repo

DAIZHIGE_URL = "https://github.com/garychowcmu/daizhigev20"


def ingest_run(ctx, source: str = "daizhige") -> dict:
    if source != "daizhige":
        return {"error": "unknown source", "source": source}
    repo = fetch_repo(ctx.cfg.raw_dir / source / "repo", DAIZHIGE_URL)
    files = enumerate_corpus(repo)
    return {"source": source, "files": len(files), "repo": str(repo)}
