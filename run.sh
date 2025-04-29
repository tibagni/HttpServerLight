#!/bin/sh

set -e # Exit early if any commands fail
exec pipenv run python3 -m app.sample "$@"
