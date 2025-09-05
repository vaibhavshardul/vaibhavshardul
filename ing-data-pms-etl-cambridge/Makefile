# Determine this makefile's path.
# Be sure to place this BEFORE `include` directives, if any.
THIS_FILE := $(lastword $(MAKEFILE_LIST))

# Git doesn't allow us to store shared hooks in .git. Instead, we make sure they're up-to-date
# whenever a make target is invoked.
.PHONY: hooks
hooks:
	@if [ -d .git/hooks ]; then cp .hooks/* .git/hooks/; fi

-include hooks # Make sure they're always up-to-date