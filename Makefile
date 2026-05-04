SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

.PHONY: lint upgrade-deps clean check dev css css-watch serve

lint:
	pre-commit run -a

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

dev:
	watchmedo auto-restart -d . -p "*.py" --recursive -- python -m dw_quote

css:
	./bin/tailwindcss -i game/static/game/css/app.css -o game/static/game/css/output.css --minify

css-watch:
	./bin/tailwindcss -i game/static/game/css/app.css -o game/static/game/css/output.css --watch

serve:
	./bin/tailwindcss -i game/static/game/css/app.css -o game/static/game/css/output.css --watch &
	python manage.py runserver 8001
