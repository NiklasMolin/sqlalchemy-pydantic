
PROJECT=sp
default: help

help:
	@echo 'Usage: make [target] ...'
	@echo
	@echo 'Targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "%-16s %s\n", $$1, $$2}'

#### DEV

_black:
	black -l 80 $(PROJECT) test

_isort:
	isort -l80 -m3 -tc -rc $(PROJECT) test

#----------- TEST --------------------------------------------------------------
test: ## Lint and unit test python code
	@$(PRE_ACTIVATE) $(MAKE) -j8 --no-print-directory \
	  test-mypy \
	  test-black \
	  test-groovy \
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
	isort -l80 -m3 -tc -rc -c $(PROJECT)

