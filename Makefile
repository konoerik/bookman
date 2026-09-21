.PHONY: install test test-cov lint format typecheck check build init import list clean-dev

install:
	uv sync

test:
	uv run pytest

test-cov:
	uv run pytest --cov

lint:
	uv run ruff check .

format:
	uv run ruff format --check .

typecheck:
	uv run mypy src/

check: lint format typecheck test

build:
	rm -rf dist
	uv build

# --- Local dev library ------------------------------------------------------
# Everything lives under .dev/ (gitignored). BOOKMAN_CONFIG keeps the dev
# config separate from the real one in ~/Library/Application Support/bookman.
# Always go through `uv run` so the venv's bookman is used, never a system one.
#
#   .dev/sample/   hand-picked source files to import (kept by clean-dev)
#   .dev/library/  the managed library bookman writes into
#   .dev/config.json

DEV_DIR    := .dev
DEV_LIB    := $(DEV_DIR)/library
DEV_CONFIG := $(DEV_DIR)/config.json
DEV_SAMPLE := $(DEV_DIR)/sample
BOOKMAN    := BOOKMAN_CONFIG=$(DEV_CONFIG) uv run bookman

# Create the dev library and make it the default for the targets below.
init:
	$(BOOKMAN) init $(DEV_LIB)

# Import the sample folder (hits Open Library). Override to import something
# else, e.g. the Gutenberg fixtures: make import SRC=tests/fixtures/books
SRC ?= $(DEV_SAMPLE)
import: init
	$(BOOKMAN) import $(SRC)

list:
	$(BOOKMAN) list

# Delete the dev library and its config; the sample folder is left alone.
clean-dev:
	rm -rf $(DEV_LIB) $(DEV_CONFIG)
