PY ?= python3

install:     ; $(PY) -m pip install -e ".[dev]"
init:        ; xqdb init
ingest:      ; xqdb ingest daizhige
normalize:   ; xqdb normalize
review:      ; xqdb review
index:       ; xqdb index
search:      ; xqdb search "$(Q)"
release:     ; xqdb release --tag $(TAG)
test:        ; $(PY) -m pytest -q
lint:        ; $(PY) -m ruff check src tests

.PHONY: install init ingest normalize review index search release test lint
