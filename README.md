# initLab Telephony

Repo containing the initLab's IVR telephony system, which enables opening of doors.

## Install


```
git clone https://github.com/initlab/initlab-telephony /var/lib/asterisk/initlab-telephony

cd /var/lib/asterisk/initlab-telephony
python3 -m venv .venv

. .venv/bin/activate
# cd /var/lib/asterisk/initlab-telephony/door_ivr/; pip install -r requirements.txt  # FIXME: pyst2 needs patches

cd /var/lib/asterisk/initlab-telephony/sounds/; ./generate-messages.sh

cd /var/lib/asterisk/initlab-telephony/; cp door_ivr/door_ivr.example.conf door_ivr/door_ivr.conf
# edit door_ivr/door_ivr.conf

# directory /usr/share/asterisk/sounds/en_US_f_Allison/ is usually owned by root, so you might need to run this in a root shell
for x in /var/lib/asterisk/initlab-telephony/sounds/files/*; do ln -s "$x" /usr/share/asterisk/sounds/en_US_f_Allison/; done

# add entries in extensions.conf to /etc/asterisk/extensions.conf
service asterisk restart
# to debug asterisk -rvvv
```

## Testing

### Automatic Tests

```
cd door_ivr/door_ivr/
python backend_mock.py &
./run-test.sh agi-test.txt
./run-test.sh agi-unknown-number.txt
./run-test.sh -  # for local testing
```

### Manual Testing

- run `docker compose up --build` - this will start a docker asterisk instance (port 5060/tcp) that has a mock backend and IVR config
- use a SIP application to connect `sip:0881234567@127.0.0.1:5060(tcp)` with password `1234` (see `docker/initlab-telephony-demo.dockerfile` ) and dial `ivr`
  - if you want to hear the sound you might need to substitute `127.0.0.1` with the address of the docker container

## TODOs:

- Document in a better way and automate.
