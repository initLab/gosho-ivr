# initLab Telephony

Repo containing the initLab's IVR telephony system, which enables opening of doors.

## Install


```
git clone git@github.com:initLab/initlab-telephony-assets /var/lib/asterisk/initlab-telephony

cd /var/lib/asterisk/initlab-telephony-assets/; ./generate-audio.sh

git clone https://github.com/initlab/initlab-telephony /var/lib/asterisk/initlab-telephony

cd /var/lib/asterisk/initlab-telephony
python3 -m venv .venv

. .venv/bin/activate
# cd /var/lib/asterisk/initlab-telephony/door_ivr; pip install -r requirements.txt  # FIXME: pyst2 needs patches

cp door_ivr/door_ivr.example.conf door_ivr/door_ivr.conf
# edit door_ivr/door_ivr.conf

# add entries in extensions.conf to /etc/asterisk/extensions.conf
# add entries in features.conf /etc/asterisk/features.conf
service asterisk restart
# to debug asterisk -rvvv
```

## Testing

```
cd door_ivr/tests/
python backend_mock.py &
./run-test.sh agi-test.txt
./run-test.sh agi-unknown-number.txt
./run-test.sh -  # for local testing
```

## TODOs:

- Document in a better way and automate.
