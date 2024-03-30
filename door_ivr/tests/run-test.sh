#/bin/bash

# Interact with the door_ivr.py
# Usage:
#   ./run-test.sh -    # for stdin
#   ./run-test.sh test-file.txt
#   ./run-test.sh test-file.txt -  # for test file and stdin

set +o pipefail -e

(cat $@ | sed 's/#.*//') | python ../door_ivr.py --handler=external --config=../door_ivr.test.conf
