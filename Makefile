init:        ; xqdb init
ingest:      ; xqdb ingest daizhige
normalize:   ; xqdb normalize
review:      ; xqdb review
index:       ; xqdb index
search:      ; xqdb search "$(Q)"
release:     ; xqdb release --tag $(TAG)
test:        ; pytest -q

.PHONY: init ingest normalize review index search release test
