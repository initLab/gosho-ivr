#!/usr/bin/env python3
"""
init Lab door IVR AGI script
"""
import abc
import argparse
import configparser
import re
import time
import typing

import requests
import requests.exceptions

from pathlib import Path

from asterisk.agi import AGI


ALLOWED_CODE_ENTERING_ATTEMPTS_COUNT = 3

DIGITS = list(range(10))

# door actions
DOOR_UNLOCK = 'unlock'
DOOR_OPEN = 'open'
DOOR_LOCK = 'lock'


class AbstractDoorManager(AGI, abc.ABC):

    def __init__(self, config_filename: str, phone_number: typing.Optional[str] = None):
        super().__init__()

        self.config = configparser.ConfigParser()
        self.config.read(config_filename)
        self.auth_backend_api_url = self.config['backend']['auth_api_url']
        self.door_backend_api_url = self.config['backend']['door_api_url']
        self.backend_access_secret = self.config['backend']['access_secret']
        self.asterisk_fallback_extension_var = self.config['asterisk']['fallback_extension_var']
        self.asterisk_fallback_extension = self.config['asterisk']['fallback_extension']
        self.backend_auth_token = None

        self.phone_number = phone_number or self.env['agi_callerid']

        self.sounds_path = Path.cwd().joinpath('initlab-telephony-assets', 'files')
        # default locale for unknown or unauthorized calls
        self.user_locale = 'bg'
        self.pin = ''

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

    def is_correct_pin(self) -> bool:
        try:
            response = requests.post(f"{self.auth_backend_api_url}/phone_access/verify_pin",
                                     data={'pin': self.pin},
                                     headers={'Authorization': f"Bearer {self.backend_auth_token}"})
            response.raise_for_status()
            return response.json()['pin'] == 'valid'
        except (requests.exceptions.RequestException, KeyError) as exc:
            self.verbose('Error verifying pin - %r' % exc)
            return False

    def get_user_locale(self) -> str:
        try:
            response = requests.get(f"{self.auth_backend_api_url}/current_user", headers={
                'Authorization': f"Bearer {self.backend_auth_token}"
            })
            response.raise_for_status()
            return response.json()['locale']
        except (requests.exceptions.RequestException, KeyError) as exc:
            raise ValueError(exc) from exc

    def get_doors(self):
        try:
            response = requests.get(f"{self.door_backend_api_url}/doors", headers={
                'Authorization': f"Bearer {self.backend_auth_token}"
            })
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, KeyError) as exc:
            raise ValueError(exc) from exc

    def perform_door_action(self, door_id, action):
        response = requests.post(f"{self.door_backend_api_url}/doors/{door_id}/{action}",
                                 headers={'Authorization': f"Bearer {self.backend_auth_token}"})
        response.raise_for_status()

    def check_assets_installed(self) -> bool:
        if not Path.is_dir(self.sounds_path):
            self.verbose('Assets not found at %s. Please install them first' % self.sounds_path)
            self.hangup()
            return False
        return True

    def stream_file_asset(self, filename, escape_digits: typing.Union[str, typing.List[int]] = '', sample_offset=0):
        return self.stream_file(str(self.sounds_path.joinpath(filename)), escape_digits, sample_offset)

    def stream_file_i18n(self, filename, escape_digits: typing.Union[str, typing.List[int]] = '', sample_offset=0):
        return self.stream_file_asset(Path(self.user_locale).joinpath(filename), escape_digits, sample_offset)

    def stream_and_capture_digit(self, filename):
        return self.stream_file_i18n(filename, escape_digits=DIGITS)  # '' on no input

    def answer_and_wait(self):
        self.answer()
        time.sleep(1)  # if we don't sleep the first part of the next audio file is skipped

    def end_call(self):
        self.stream_file_i18n('goodbye')
        self.hangup()

    def answer_wait_greet_stream_and_end_call(self, filename):
        self.answer_and_wait()
        self.stream_file_i18n('welcome')
        self.stream_file_i18n(filename)
        self.end_call()

    def prompt_for_pin(self):
        next_digit = self.stream_and_capture_digit('enter_pin')
        self.pin += next_digit
        while next_digit != '#':
            # we give a bit more time for the first digit
            next_digit = self.wait_for_digit(4000 if len(self.pin) else 12000)
            if not next_digit:
                raise ValueError("Failed to enter pin within the timeout")
            self.pin += next_digit

        self.pin = self.pin.rstrip('#')

    def user_knows_the_pin(self) -> bool:
        for attempt_number in range(ALLOWED_CODE_ENTERING_ATTEMPTS_COUNT):
            try:
                self.prompt_for_pin()
            except ValueError:
                # pin entry timed out, enter_pin message will be played again
                self.pin = ''
            else:
                if self.is_correct_pin():
                    return True
                else:
                    self.pin = self.stream_and_capture_digit('wrong_pin')

    def handle_choices_menu(self, doors):
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

        selection = ''

        while True:  # timeout handled inside
            # TODO: consider getting the door statuses when there is an API for this
            for door_number in door_action_choices:
                if not selection:
                    selection = self.stream_file_i18n('door_prompt_' + door_number, escape_digits=DIGITS)

            if not selection:
                selection = self.stream_file_asset('waiting_on_input', escape_digits=DIGITS)
                # for some reason wait_for_digit didn't work for 5 min...
            if not selection:
                self.end_call()
                return

            if selection not in door_action_choices:
                # wrong selection
                selection = self.stream_file_i18n('wrong_selection', escape_digits=DIGITS)
            elif selection == '9':
                lockable_door_ids = [door['id'] for door in doors if DOOR_LOCK in door['supported_actions']]
                if not lockable_door_ids:
                    selection = self.stream_file_i18n('lock_failed', escape_digits=DIGITS)
                else:
                    try:
                        for door_id in lockable_door_ids:
                            self.perform_door_action(door_id, 'lock')
                        # Ideally we would wait until the door is confirmed to be locked,
                        # however, there is no such API at the moment.
                        self.stream_file_i18n('door_locked')
                        self.end_call()  # nothing more to do - let's save some actions for the user
                        return
                    except requests.exceptions.RequestException as exc:
                        # TODO: check that all doors are locked when there is an API
                        self.verbose('Error locking doors - %r' % exc)
                        selection = self.stream_file_i18n('action_unsuccessful', escape_digits=DIGITS)
                        # we don't want to hang up - the user can retry
            else:
                door = doors_map[int(selection)]
                try:
                    for action in [DOOR_UNLOCK, DOOR_OPEN]:
                        if action in door['supported_actions']:
                            self.perform_door_action(door['id'], action)
                    selection = self.stream_file_i18n('door_opened_' + selection, escape_digits=DIGITS)
                except requests.exceptions.RequestException as exc:
                    self.verbose('Error opening the door %r - %r' % (door, exc))
                    selection = self.stream_file_i18n('action_unsuccessful', escape_digits=DIGITS)

    @abc.abstractmethod
    def handle_phone_call(self):
        raise NotImplemented


class ExternalPhoneDoorManager(AbstractDoorManager):

    def handle_phone_call(self):
        self.verbose('External phone door IVR received a call from %r' % self.phone_number)

        if not self.check_assets_installed():
            return

        try:
            self.backend_auth_token = self.get_auth_token()
        except ValueError as e:
            self.verbose('Getting auth failed for %r - %r' % (self.phone_number, e))
            self.answer_wait_greet_stream_and_end_call('service_unavailable')
            return

        if self.backend_auth_token is None:
            # phone number is unknown
            fallback_extension = self.get_variable(self.asterisk_fallback_extension_var) \
                                 or str(self.asterisk_fallback_extension)
            self.answer_and_wait()
            self.stream_file_i18n('welcome')
            self.stream_file_i18n('redirecting_to_public_phone')
            self.set_extension(fallback_extension)
            self.set_priority(1)
            return

        self.user_locale = self.get_user_locale()

        doors = self.get_doors()

        if not any(door['supported_actions'] for door in doors):
            self.answer_wait_greet_stream_and_end_call('insufficient_permissions')
            return

        self.answer_and_wait()
        self.pin = self.stream_and_capture_digit('welcome')  # initialize pin

        if not self.user_knows_the_pin():
            self.end_call()
            return

        self.handle_choices_menu(doors)


class PayphoneDoorManager(AbstractDoorManager):

    def handle_phone_call(self):
        self.verbose("Payphone door IVR received a call")

        if not self.check_assets_installed():
            return

        self.answer_and_wait()

        # get the first digit of the phone number, overwriting the value from the constructor
        self.phone_number = self.stream_and_capture_digit('welcome')
        digit = self.stream_and_capture_digit('enter_phone')
        while digit != '#':
            self.phone_number += digit
            digit = self.wait_for_digit(12000)

        self.verbose("Phone number %r entered on the payphone" % self.phone_number)

        try:
            self.backend_auth_token = self.get_auth_token()
        except ValueError as e:
            self.verbose('Getting auth failed for %r - %r' % (self.phone_number, e))
            self.stream_file_i18n('service_unavailable')
            self.end_call()
            return

        if self.backend_auth_token is None:
            # phone number is unknown
            fallback_extension = self.get_variable(self.asterisk_fallback_extension_var) \
                                 or str(self.asterisk_fallback_extension)
            self.stream_file_i18n('redirecting_to_public_phone')
            self.set_extension(fallback_extension)
            self.set_priority(1)
            return

        self.user_locale = self.get_user_locale()

        doors = self.get_doors()

        if not any(door['supported_actions'] for door in doors):
            self.stream_file_i18n('insufficient_permissions')
            self.end_call()
            return

        if not self.user_knows_the_pin():
            self.end_call()
            return

        self.handle_choices_menu(doors)


class InternalPhoneDoorManager(AbstractDoorManager):

    def handle_phone_call(self):
        self.verbose("Internal door IVR received a call from %r" % self.phone_number)

        if not self.check_assets_installed():
            return

        self.phone_number = self.config['internal_phones_mapping'].get(self.phone_number, None)

        if not self.phone_number:
            self.answer_wait_greet_stream_and_end_call('insufficient_permissions')
            return

        try:
            self.backend_auth_token = self.get_auth_token()
        except ValueError as e:
            self.verbose('Getting auth failed for %r - %r' % (self.phone_number, e))
            self.answer_wait_greet_stream_and_end_call('service_unavailable')
            return

        if self.backend_auth_token is None:
            # phone number is unknown
            self.answer_wait_greet_stream_and_end_call('insufficient_permissions')
            return

        self.user_locale = self.get_user_locale()

        doors = self.get_doors()

        if not any(door['supported_actions'] for door in doors):
            self.answer_wait_greet_stream_and_end_call('insufficient_permissions')
            return

        self.answer_and_wait()
        self.handle_choices_menu(doors)


class InCallDoorManager(AbstractDoorManager):

    def handle_phone_call(self):
        channel = self.env['agi_channel']  # e.g., "SIP/bigroom-0000002"
        door_id = self.phone_number  # FIXME: this is a hack
        self.verbose("In-call door IVR received a call from %r for door %s" % (channel, door_id))

        match = re.fullmatch('SIP/(.+)-.+', channel)
        self.phone_number = match.group(1) if match else None

        self.phone_number = self.config['internal_phones_mapping'].get(self.phone_number, None)

        if not self.phone_number:
            self.answer_wait_greet_stream_and_end_call('insufficient_permissions')
            return

        try:
            self.backend_auth_token = self.get_auth_token()
        except ValueError as e:
            self.verbose('Getting auth failed for %r - %r' % (self.phone_number, e))
            self.answer_wait_greet_stream_and_end_call('service_unavailable')
            return

        if self.backend_auth_token is None:
            # phone number is unknown
            self.answer_wait_greet_stream_and_end_call('insufficient_permissions')
            return

        self.user_locale = self.get_user_locale()

        doors = self.get_doors()

        if not any(door['supported_actions'] for door in doors):
            self.answer_wait_greet_stream_and_end_call('insufficient_permissions')
            return

        doors_map = {str(door.get('number')): door for door in doors}

        try:
            self.perform_door_action(doors_map[door_id]['id'], DOOR_OPEN)
        except requests.exceptions.RequestException as exc:
            self.verbose('Error opening the door %r - %r' % (doors_map[door_id], exc))
            self.stream_file_i18n('action_unsuccessful')
            return

        self.stream_file_i18n(f'door_opened_{door_id}')


def main():
    parser = argparse.ArgumentParser(description='init Lab door IVR AGI script')
    parser.add_argument('--config', help='location of the configuration file', required=True)
    parser.add_argument('--handler', choices=['external', 'payphone', 'internal', 'in-call'],
                        help='handler to use - one of %(choices)s',
                        required=True)
    parser.add_argument('--phone', help='phone number (default to getting it from caller id)', default=None)
    args = parser.parse_args()
    door_manager_class = {
        'external': ExternalPhoneDoorManager,
        'payphone': PayphoneDoorManager,
        'internal': InternalPhoneDoorManager,
        'in-call': InCallDoorManager,
    }[args.handler]
    assert issubclass(door_manager_class, AbstractDoorManager)
    door_manager = door_manager_class(phone_number=args.phone, config_filename=args.config)
    door_manager.handle_phone_call()


if __name__ == '__main__':
    main()
