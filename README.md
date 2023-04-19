# initLab Telephony

Repo containing the initLab's IVR telephony system, which enables opening of doors.

This was codenamed `gosho-ivr` due to being able to open the initlab doors.


## Install


```
git clone https://github.com/initlab/initlab-telephony /var/lib/asterisk/gosho-ivr

cd /var/lib/asterisk/gosho-ivr
python -m vevn .venv

. .venv/bin/activate
# pip install -r requirements.txt  # FIXME: pyst2 needs patches

cd /var/lib/asterisk/gosho-ivr/sounds/; ./generate-messages.sh

cp door_ivr/door_ivr.example.conf door_ivr/door_ivr.conf
# edit door_ivr/door_ivr.conf

for x in /var/lib/asterisk/gosho-ivr/sounds/files/*; do ln -s "$x" /usr/share/asterisk/sounds/en_US_f_Allison/; done

# add entries in extensions.conf to /etc/asterisk/extensions.conf
service asterisk restart
# to debug asterisk -rvvv
```

## TODOs:

- Upload tick-tock wav (we might end up changing the tune).
- Document in a better way and automate.
- Remove references to `gosho-ivr`
