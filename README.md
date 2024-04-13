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

### Manual Testing

- run `docker compose up --build` - this will start a docker asterisk instance (port 5060/tcp) that has a mock backend and IVR config
- use a SIP application to connect `sip:0881234567@127.0.0.1:5060(tcp)` with password `1234` (see `docker/initlab-telephony-demo.dockerfile` ) and dial `ivr`
  - if you want to hear the sound you will need to substitute `127.0.0.1` with the address of the docker container
    - to get the docker ip you can use the following command `docker-compose exec asterisk-initlab-telephony bash -c 'ip a | grep 172'`
  - to execute things in the container `docker-compose exec asterisk-initlab-telephony asterisk -rvvvdd`

## TODOs:

- Document better and automate.
- Better tests.
- Document how to test the other handlers.
