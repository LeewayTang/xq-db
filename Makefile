PY ?= python3

install:     ; $(PY) -m pip install -e ".[dev]"
init:        ; xqdb init
ingest:      ; xqdb ingest daizhige
normalize:   ; xqdb normalize
review:      ; xqdb review
index:       ; xqdb index
search:      ; xqdb search "$(Q)"
place:       ; xqdb place "$(NAME)"
near:        ; xqdb near $(LAT) $(LON) --radius $(RADIUS)
when:        ; xqdb when $(START) $(END)
release:     ; xqdb release --tag $(TAG)
test:        ; $(PY) -m pytest -q
lint:        ; $(PY) -m ruff check src tests

.PHONY: install init ingest normalize review index search place near when release test lint
