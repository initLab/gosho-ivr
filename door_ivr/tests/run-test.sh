#/bin/bash

(cat "$1" | sed 's/#.*//'; cat) | python ../door_ivr.py --config=../door_ivr.test.conf
