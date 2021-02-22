
PROJECT=sp
default: help

help:
	@echo 'Usage: make [target] ...'
	@echo
	@echo 'Targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "%-16s %s\n", $$1, $$2}'

.PHONY: *
#### DEV

_black:
	black -l 100 $(PROJECT) test

_isort:
	isort -l100 -m3 -tc -rc $(PROJECT) test

#----------- TEST --------------------------------------------------------------
test: ## Lint and unit test python code
	@$(PRE_ACTIVATE) $(MAKE) -j8 --no-print-directory \
	  test-mypy \
	  test-black \
	  test-pylint \
	  test-unit \
	  test-isort

test-check: ## Lint and unit test python code
	@$(PRE_ACTIVATE) $(MAKE) -j8 --no-print-directory \
	  test-pylint \
	  test-mypy \
	  test-black \
	  test-isort

test-black:
	black -l 100 $(PROJECT) --check --exclude version.py

test-mypy:
	mypy $(PROJECT)

test-pylint:
	pylint -f parseable --rcfile=setup.cfg -j 4 $(PROJECT)

test-unit:
	@rm -f var/.coverage var/.coverage.*
	pytest $(EXTRA_JAR) test -rf -q --cov $(PROJECT) \
	  --cov-branch  --cov-report term $(PYTESTFLAGS)

test-isort:
	isort -l100 -m3 -tc -rc -c $(PROJECT)

build:
	python3 -m build

upload-test:
	python3 -m twine upload --skip-existing --repository testpypi dist/* -u __token__ -p "$(PYPI_TEST)"

upload:
	python3 -m twine upload --skip-existing --repository pypi dist/* -u __token__ -p "$(PYPI)"
