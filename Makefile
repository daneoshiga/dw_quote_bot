SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

.PHONY: lint upgrade-deps clean check

lint:
	pre-commit run -a -v

objects = $(wildcard requirements/*.in)
outputs := $(objects:.in=.txt)

requirements: $(outputs)

%.txt: %.in
	pip-compile -v --output-file $@ $<

upgrade-deps: clean requirements
	pip-sync $(outputs)

check:
	@which pip-compile > /dev/null

clean: check
	- rm requirements/*.txt
