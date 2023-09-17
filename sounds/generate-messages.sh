#!/bin/bash
set -x -e

create_audio_file () {
    espeak-ng -s 140 -l en "$2" -w >(ffmpeg -i - -y -sample_fmt s16 -ar 8000 files/"$1".wav)
}

create_ding_dong_file () {
    sample_rate=8000
    duration=2  # Duration of each "ding" and "dong" sound in seconds
    fade_in_duration=1  # Fade-in duration in seconds
    fade_out_duration=1  # Fade-out duration in seconds
    sox -n -r $sample_rate -e signed-integer -b 16 -c 1 files/_ding.wav synth $duration sine 240 fade h $fade_in_duration $duration $fade_out_duration
    sox -n -r $sample_rate -e signed-integer -b 16 -c 1 files/_dong.wav synth $duration sine 270 fade h $fade_in_duration $duration $fade_out_duration

    sox -e signed-integer -b 16 -r $sample_rate files/_ding.wav files/_dong.wav files/clock_tick_tock_src.wav
    rm files/_ding.wav files/_dong.wav
}

mkdir -p files/

create_audio_file enter_pin                     'Enter pin'
create_audio_file wrong                         'Wrong'
create_audio_file service_unavailable           'Error. Service is temporary unavailable. Contact admins.'
create_audio_file redirecting_to_public_phone   'Phone number unauthorized. Redirecting...'
create_audio_file door_command_prompt           'Please enter door number to unlock and open, and 9 to lock everything.'
create_audio_file wrong_choice                  'Invalid choice.'
create_audio_file insufficient_permissions      'Insufficient permissions.'
create_audio_file door_opened                   'Door opened.'
create_audio_file door_locked                   'Locked.'
create_audio_file opening_door                  'Opening door.'
create_audio_file locking_doors                 'Locking...'
create_audio_file action_unsuccessful           'Action unsuccessful'
create_audio_file goodbye                       'Goodbye'

# generate files/clock_tick_tock_src.wav
if test ! -e files/clock_tick_tock_src.wav; then
    create_ding_dong_file
fi

ffmpeg -stream_loop 15 -i files/clock_tick_tock_src.wav -y -sample_fmt s16 -ar 8000 -ac 1 files/waiting_on_input.wav
