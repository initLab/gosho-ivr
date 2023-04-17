#!/bin/bash
set -x -e

create_audio_file () {
    espeak-ng -s 140 -l en "$2" -w >(ffmpeg -i - -y -sample_fmt s16 -ar 8000 files/"$1".wav)
}

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

ffmpeg -stream_loop 15 -i files/clock_tick_tock_src.wav -y -sample_fmt s16 -ar 8000 -ac 1 files/waiting_on_input.wav
