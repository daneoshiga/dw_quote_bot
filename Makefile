SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

lint:
	pre-commit run -a -v

upgrade-deps:
	pip-compile --upgrade requirements/prod.in --output-file requirements/prod.txt
	pip-compile --upgrade requirements/parse.in --output-file requirements/parse.txt

.PHONY: lint upgrade
