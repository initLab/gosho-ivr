# initLab Telephony

Repo containing the initLab's IVR telephony system, which enables opening of doors.

## Install


```
git clone https://github.com/initlab/initlab-telephony /var/lib/asterisk/initlab-telephony

cd /var/lib/asterisk/initlab-telephony
python3 -m venv .venv

. .venv/bin/activate
# cd /var/lib/asterisk/initlab-telephony/door_ivr; pip install -r requirements.txt  # FIXME: pyst2 needs patches

cd /var/lib/asterisk/initlab-telephony/sounds/; ./generate-messages.sh

cp door_ivr/door_ivr.example.conf door_ivr/door_ivr.conf
# edit door_ivr/door_ivr.conf

for x in /var/lib/asterisk/initlab-telephony/sounds/files/*; do ln -s "$x" /usr/share/asterisk/sounds/en_US_f_Allison/; done

# add entries in extensions.conf to /etc/asterisk/extensions.conf
service asterisk restart
# to debug asterisk -rvvv
```

## Testing

```
cd door_ivr/door_ivr/
python backend_mock.py &
./run-test.sh agi-test.txt
./run-test.sh agi-unknown-number.txt
./run-test.sh -  # for local testing
```

## TODOs:

- Document in a better way and automate.
