#!/usr/bin/env python3
"""
init Lab door IVR AGI script
"""

import argparse
import configparser
import time
import typing

import requests
import requests.exceptions

from pathlib import Path

from asterisk.agi import AGI


ALLOWED_CODE_ENTERING_ATTEMPTS_COUNT = 3
PIN_LENGTH = 6

# door actions
DOOR_UNLOCK = 'unlock'
DOOR_OPEN = 'open'
DOOR_LOCK = 'lock'


class DoorManager(AGI):

    def __init__(self, phone_number: typing.Optional[str] = None, config_filename: str = 'door_ivr.conf'):
        super().__init__()

        config = configparser.ConfigParser()
        config.read(config_filename)
        self.auth_backend_api_url = config['backend']['auth_api_url']
        self.door_backend_api_url = config['backend']['door_api_url']
        self.backend_access_secret = config['backend']['access_secret']
        self.asterisk_fallback_extension_var = config['asterisk']['fallback_extension_var']
        self.asterisk_fallback_extension = config['asterisk']['fallback_extension']
        self.backend_auth_token = None

        self.phone_number = phone_number or self.env['agi_callerid']

        self.sounds_path = Path.cwd().joinpath('initlab-telephony-assets/files')
        # default locale for unknown or unauthorized calls
        self.user_locale = 'bg'

    def get_auth_token(self) -> typing.Optional[str]:
        """
        Return an OAuth token representing the user with the phone in question
        or return None if the user is not found.

        :raises ValueError: on any exception
        """
        try:
            response = requests.post(f"{self.auth_backend_api_url}/phone_access/phone_number_token",
                                     data={
                                         'secret': self.backend_access_secret,
                                         'phone_number': self.phone_number,
                                     })
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()['auth_token']['token']
        except (requests.exceptions.RequestException, KeyError) as exc:
            raise ValueError(exc) from exc

    def get_user_locale(self) -> str:
        try:
            response = requests.get(f"{self.auth_backend_api_url}/current_user", headers={
                'Authorization': f"Bearer {self.backend_auth_token}"
            })
            response.raise_for_status()
            return response.json()['locale']
        except (requests.exceptions.RequestException, KeyError) as exc:
            raise ValueError(exc) from exc

    def stream_file_asset(self, filename, escape_digits='', sample_offset=0):
        return self.stream_file(str(self.sounds_path.joinpath(filename)), escape_digits, sample_offset)

    def stream_file_i18n(self, filename, escape_digits='', sample_offset=0):
        return self.stream_file_asset(Path(self.user_locale).joinpath(filename), escape_digits, sample_offset)

    def end_call(self):
        self.stream_file_i18n('goodbye')
        self.hangup()

    def prompt_for_pin(self) -> str:
        pin = ''
        next_digit = self.stream_file_i18n('enter_pin', escape_digits=list(range(10)))  # '' is returned on non input
        pin += next_digit
        while len(pin) < PIN_LENGTH:
            next_digit = self.wait_for_digit(4000 if len(pin) else 12000)  # we give a bit more time for the first digit
            if not next_digit:
                raise ValueError("Failed to enter pin within the timeout")
            pin += next_digit
        return pin

    def is_correct_pin(self, pin: str) -> bool:
        try:
            response = requests.post(f"{self.auth_backend_api_url}/phone_access/verify_pin",
                                     data={'pin': pin},
                                     headers={'Authorization': f"Bearer {self.backend_auth_token}"})
            response.raise_for_status()
            return response.json()['pin'] == 'valid'
        except (requests.exceptions.RequestException, KeyError) as exc:
            self.verbose('Error verifying pin - %r' % exc)
            return False

    def user_knows_the_pin(self) -> bool:
        for attempt_number in range(ALLOWED_CODE_ENTERING_ATTEMPTS_COUNT):
            try:
                pin = self.prompt_for_pin()
            except ValueError:
                self.stream_file_i18n('pin_entry_timed_out')  # maybe we need to differentiate between the two?
            else:
                if self.is_correct_pin(pin):
                    return True
                else:
                    self.stream_file_i18n('wrong_pin')

    def handle_phone_call(self):
        is_bulfon = self.get_variable('bulfon') not in {'', '0'}
        self.verbose('Door IVR received a call from %r (is_bulfon=%s)' % (self.phone_number, is_bulfon), level=1)

        if not Path.is_dir(self.sounds_path):
            self.verbose('Assets not found at %s. Please install them first' % self.sounds_path)
            self.hangup()
            return

        self.answer()
        time.sleep(1)  # if we don't sleep the first part of the next audio file is skipped

        try:
            self.backend_auth_token = self.get_auth_token()
        except ValueError as e:
            self.verbose('Getting auth failed for %r - %r' % (self.phone_number, e))
            self.stream_file_i18n('welcome')
            self.stream_file_i18n('service_unavailable')
            self.end_call()
            return

        if self.backend_auth_token is None:
            # phone number is unknown
            fallback_extension = self.get_variable(self.asterisk_fallback_extension_var) \
                                 or str(self.asterisk_fallback_extension)
            self.stream_file_i18n('welcome')
            self.stream_file_i18n('redirecting_to_public_phone')
            self.set_extension(fallback_extension)
            return

        self.user_locale = self.get_user_locale()
        self.stream_file_i18n('welcome')

        if not self.user_knows_the_pin():
            self.end_call()
            return

        try:
            response = requests.get(f"{self.door_backend_api_url}/doors",
                                    headers={'Authorization': f"Bearer {self.backend_auth_token}"})
            response.raise_for_status()
            doors = response.json()
            if not any(door['supported_actions'] for door in doors):
                self.stream_file_i18n('insufficient_permissions')
                self.end_call()
                return
        except (requests.exceptions.RequestException, KeyError) as exc:
            self.verbose('Error getting door properties - %r' % exc)
            self.stream_file_i18n('service_unavailable')
            self.end_call()
            return

        # backwards compatible if not all doors have numbers 1-8
        available_numbers = set(range(1, 9))
        free_numbers = iter(sorted(available_numbers - set(door.get('number', -1) for door in doors)))

        doors_map = {
           door.get('number') if door.get('number') in available_numbers else next(free_numbers): door
           for door in doors
        }

        assert len(doors) == len(doors_map), 'There are door number duplicates!'

        door_action_choices = [
            str(door_number) for door_number, door in doors_map.items()
            if {DOOR_UNLOCK, DOOR_OPEN}.intersection(set(door['supported_actions']))
        ] + ['9']

        while True:  # timeout handled inside
            # TODO: consider getting the door statuses when there is an API for this
            # TODO: split door command prompt into separate files, speak only the authorized ones
            choice = self.stream_file_i18n('door_command_prompt', door_action_choices)
            if not choice:
                choice = self.stream_file_asset('waiting_on_input', escape_digits=list(map(str, range(10))))
                # for some reason wait_for_digit didn't work for 5 min...
            if not choice:
                self.end_call()
                return

            if choice not in door_action_choices:
                # wrong choice
                self.stream_file_i18n('wrong_choice')
            elif choice == '9':
                lockable_door_ids = [door['id'] for door in doors if DOOR_LOCK in door['supported_actions']]
                if not lockable_door_ids:
                    self.stream_file_i18n('lock_failed')
                else:
                    try:
                        self.stream_file_i18n('locking_doors')
                        for door_id in lockable_door_ids:
                            response = requests.post(f"{self.door_backend_api_url}/doors/{door_id}/lock",
                                                     headers={'Authorization': f"Bearer {self.backend_auth_token}"})
                            response.raise_for_status()
                        # Ideally we would wait until the door is confirmed to be locked,
                        # however, there is no such API at the moment.
                        self.stream_file_i18n('door_locked')
                        self.end_call()  # nothing more to do - let's save some actions for the user
                        return
                    except requests.exceptions.RequestException as exc:
                        # TODO: check that all doors are locked when there is an API
                        self.verbose('Error locking doors - %r' % exc)
                        self.stream_file_i18n('action_unsuccessful')
                        # we don't want to hang up - the user can retry
            else:
                self.stream_file_i18n('opening_door')
                # TODO: say door name instead
                # self.say_digits(choice)
                door = doors_map[int(choice)]
                try:
                    for action in [DOOR_UNLOCK, DOOR_OPEN]:
                        if action in door['supported_actions']:
                            response = requests.post(f"{self.door_backend_api_url}/doors/{door['id']}/{action}",
                                                     headers={'Authorization': f"Bearer {self.backend_auth_token}"})
                            response.raise_for_status()
                    self.stream_file_i18n('door_opened')
                except requests.exceptions.RequestException as exc:
                    self.verbose('Error opening the door %r - %r' % (door, exc))
                    self.stream_file_i18n('action_unsuccessful')


def main():
    parser = argparse.ArgumentParser(description='init Lab door IVR AGI script')
    parser.add_argument('--phone', help='phone number (default to getting it from caller id)', default=None)
    parser.add_argument('--config', help='location of the configuration file', default='door_ivr.conf')
    args = parser.parse_args()
    door_manager = DoorManager(phone_number=args.phone, config_filename=args.config)
    door_manager.handle_phone_call()


if __name__ == '__main__':
    main()
