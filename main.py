#! /usr/bin/env python

import json
import sys
import random
import argparse
import csv
import itertools
import copy
import os.path

# The arguments used to generate the JSON
parser = argparse.ArgumentParser()
parser.add_argument('-t', '--trade-value', dest='trade_value', help='Trade value')
parser.add_argument('-a', '--amend-value', dest='amend_immediate', help='Amend immediate value')
parser.add_argument('-c', '--cancel-value', dest='cancel_immediate', help='Cancel immediate value')
parser.add_argument('-w', '--within', dest='within_value', default='1000', help='Within value')
parser.add_argument('-d', '--delay', dest='delay_value', default='2000', help='Delay value')
parser.add_argument('-u', '--users', dest='users_value', default='1-6', help='Numbers of users to be generated')
parser.add_argument('json_template', metavar='FILE')

CLI_ARGUMENTS = parser.parse_args()

TEST_BLOCK_TEMPLATES = {
    1: [
        'trade1',
        100,
        'cancel_immediate',
        0,
        'amend_immediate',
        0
    ],
    2: [
        'reconnect'
    ],
    3: [
        'full_recovery'
    ],
    4: [
        'recovery'
    ]
}


############
# UTILITIES
def merge_dicts(dict1: dict, dict2: dict) -> dict:
    res = {**dict1, **dict2}
    return res


# def is_valid_file(parser, arg):
#     if not os.path.exists(arg):
#         parser.error("The file %s does not exist!" % arg)
#     else:
#         return open(arg, 'r')


########
# LOGIC
class JsonRandomizer:
    """Class will handle all operations related to parsing and generating the JSON"""
    def __init__(self, json_file: str) -> None:
        self.json_dict = {}
        self.json_file = json_file

    def _parse_json_file(self) -> None:
        with open(self.json_file, 'r') as f:
            json_dict = json.load(f)
        self.json_dict = json_dict

    def generate_json_file(self, args: dict, users_list: list, value_generator: 'ValueHandler'):
        self._parse_json_file()

        # Make copies of the template
        json_skeleton = copy.deepcopy(self.json_dict)
        # user_set = copy.deepcopy(json_skeleton['users'][0])

        # Clear the list
        json_skeleton['users'].clear()

        for i in range(args.get('users_value')):
            # Grab the users copied from the CSV file
            user = users_list[i]

            # Pass the users
            temp_user_set = {
                'user': user,
                'login': user,
                'connect': user,
                'wait_login_response': user
            }

            # Generate random template
            template = value_generator.create_template()

            # Merge the 2 dictionaries
            temp_user_set = merge_dicts(temp_user_set, template)
            json_skeleton['users'].append(temp_user_set)

        with open('generated.json', 'w') as f:
            f.write(json.dumps(copy.deepcopy(json_skeleton), indent=2))


class ValueHandler:
    """This class will handle collecting and generating random values"""
    def __init__(self) -> None:
        self.args = {}
        self.generated_args = {}
        self.random_users = []

    def _collect_arguments(self) -> None:
        self.args = vars(CLI_ARGUMENTS)

    def create_template(self) -> dict:
        self._generate_values()

        template = {
            'test_recovery': random.choice([True, False]),
            'delay_between_two_tests': self.generated_args['delay_value'],
            'reset_seq_numbers_on_logon': random.choice([True, False]),
            'tests': [
            ]
        }

        test_blocks = self.create_test_blocks(random.randint(1, 5))
        template.get('tests').extend(test_blocks)

        return template

    def create_test_blocks(self, number_of_blocks: int) -> list:
        OPTIONAL_FIELDS = {
            'trade1': {
                'run_full_recovery_test': random.choice([True, False]),  # trade1
                'run_recovery_with_range': random.randint(1, 10),  # trade1
            },
            'reconnect': {
                'reset_seq_numbers_on_logon': random.choice([True, False]),  # reconnect
            },
            'recovery': {
                'seq_num_range': random.randint(1, 10)  # recovery
            }
        }

        # Add extra options in the template based on the test type
        test_blocks = list()
        keys_list = list(TEST_BLOCK_TEMPLATES.keys())

        for i in range(number_of_blocks):
            # Generate random values for each iteration
            self._generate_values()

            # Initialize empty test template block
            test_block = [
                {
                    'template': [],
                    'within': self.generated_args['within_value'],
                    'repeat': self.generated_args['repeat']
                }
            ]

            # Get a random value from the block template
            random_key = random.choice(keys_list)
            random_value = TEST_BLOCK_TEMPLATES[random_key]

            # Based on the random value, add the optional_fields
            if 'trade1' in random_value:
                test_block[0].update(OPTIONAL_FIELDS.get('trade1'))
            elif 'reconnect' in random_value:
                test_block[0].update(OPTIONAL_FIELDS.get('reconnect'))
            elif 'recovery' in random_value:
                test_block[0].update(OPTIONAL_FIELDS.get('recovery'))

            test_block[0]['template'].extend(random_value)
            test_blocks.extend(test_block)

        return test_blocks

    def _generate_values(self) -> None:
        self._collect_arguments()

        for key, value in self.args.items():
            if '-' in value:
                value1, value2 = value.split('-')
                random_value = random.randint(int(value1), int(value2))
            else:
                random_value = value
            self.generated_args[key] = random_value

        # Perform check for trade_value
        if (int(self.generated_args.get('trade_value')) < int(self.generated_args.get('cancel_immediate')) +
                int(self.generated_args.get('amend_immediate'))):
            print('Trade value cannot be lower than cancel and amend sum.')
            sys.exit(1)

        # Randomize repeat value 1-10
        self.generated_args['repeat'] = str(random.randint(1, 10))

    def generate_random_user(self) -> None:
        with open('users.csv', 'r', newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=' ', quotechar='|')
            sliced_reader = itertools.islice(reader, 0, self.generated_args.get('users_value'))
            random_users = [user[0].split(',')[0].strip('"') for user in list(sliced_reader)]
            self.random_users = random_users


def setup():
    # Initialize the Value Handler object
    value_handler = ValueHandler()
    # value_handler.generate_values()
    # a = value_handler.create_test_blocks(3)
    # print(a)
    value_handler.generate_random_user()
    value_handler.create_template()

    # Initialize the JSON randomizer object
    json_worker = JsonRandomizer(CLI_ARGUMENTS.json_template)
    json_worker.generate_json_file(args=value_handler.generated_args, users_list=value_handler.random_users,
                                 value_generator=value_handler)


def main():
    setup()


if __name__ == '__main__':
    main()
