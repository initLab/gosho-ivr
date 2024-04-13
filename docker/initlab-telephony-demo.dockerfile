FROM debian:11

RUN apt-get update && apt-get install -y asterisk python3 python3-pip python3-venv espeak-ng ffmpeg sox git vim-nox iproute2

RUN mkdir -p /var/lib/asterisk/initlab-telephony/sounds

RUN python3 -m venv /var/lib/asterisk/initlab-telephony/.venv

RUN /var/lib/asterisk/initlab-telephony/.venv/bin/pip install git+https://github.com/jfernandz/pyst2@598fbfc8a1000855ef590bb48dd9b0fc18478b69
COPY door_ivr/requirements.txt /var/lib/asterisk/initlab-telephony/door_ivr/
RUN /var/lib/asterisk/initlab-telephony/.venv/bin/pip install -r /var/lib/asterisk/initlab-telephony/door_ivr/requirements.txt

RUN cat >/etc/asterisk/sip.conf <<\EOF
[general]
transport=tcp
rtcp_mux=yes
tcpenable=yes  ; Enable TCP support - this is easier for debugging
udpbindaddr=0.0.0.0  ; Listen on all available UDP addresses
tcpbindaddr=0.0.0.0  ; Listen on all available TCP addresses

[0881234567]
type=friend
username=0881234567
secret=1234
host=dynamic
rtcp_mux=yes
context=incoming
allowguest=yes
allow=all
transport=tcp
callerid="0881234567" <0881234567>

[0880000000]
; this is id that is not registered
type=friend
username=0880000000
secret=1234
host=dynamic
rtcp_mux=yes
context=incoming
allowguest=yes
allow=all
transport=tcp
callerid="0880000000" <0880000000>
EOF

COPY door_ivr/door_ivr.py /var/lib/asterisk/initlab-telephony/door_ivr/door_ivr.py
COPY door_ivr/door_ivr.test.conf /var/lib/asterisk/initlab-telephony/door_ivr/door_ivr.conf
COPY door_ivr/tests/backend_mock.py /tmp/backend_mock.py

COPY asterisk-conf/features.conf /etc/asterisk/
COPY asterisk-conf/extensions.conf /etc/asterisk/

EXPOSE 5060/tcp
EXPOSE 5060/udp

WORKDIR /var/lib/asterisk/

# TODO: improve the starting
CMD ["bash", "-c", "ip a; python3 /tmp/backend_mock.py & asterisk -fvvvddd & wait -n; exit $?"]
