#!/usr/bin/env python3
"""Usage:
        teampass list
        teampass show [-c] <passname>
        teampass find <passname>
        teampass insert <passname>
        teampass generate <passname>
        teampass shell [-c]
        teampass dump

Retrieve or insert passwords into Teampass.

Arguments:
  passname    password name

Options:
  -c --clip   write to clipboard
  -h --help   show this help
"""
import sys
import re
import json
from getpass import getpass
from os.path import expanduser
try:
    import requests
    from docopt import docopt
    from xkcdpass import xkcd_password as xp
    import pyperclip
    from prompt_toolkit.contrib.completers import WordCompleter
    from prompt_toolkit import prompt
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.interface import AbortAction
except ImportError:
    print("Some modules are missing. Try something like:"
          "`pip install requests docopt xkcdpass pyperclip prompt_toolkit`.")
    sys.exit(1)


class TeampassClient:
    def __init__(self, api_endpoint, api_key, categories):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.categories = categories
        self.items = self.get_items()
        self.output_to_clipboard = False
        self.history = FileHistory(expanduser('~/.teampass_history'))

    def get_items(self):
        results = {}
        for category, category_name in self.categories.items():
            url = "{0}/read/category/{1}?apikey={2}"\
                .format(self.api_endpoint, category, self.api_key)
            req = requests.get(url)
            if req.status_code != 200:
                raise ValueError('Unexpected HTTP return code: {0}\n'
                                 'Request body: {1}'
                                 .format(req.status_code, req.text))
            results[category_name] = req.json()
        return results

    def get_passnames(self):
        pass_list = []
        for category, items in self.items.items():
            for item, value in items.items():
                pass_list.append(
                    ("{0}/{1}/{2}"\
                    .format(category, value['label'], value['login'])))
        return pass_list

    def get_folder_id(self, folder):
        for key, value in self.categories.items():
            if value == folder:
                return key
        raise ValueError('No folder id known for "{0}".'.format(folder))

    def list_passnames(self):
        for passname in self.get_passnames():
            print('{0}'.format(passname))

    def get_password(self, passname):
        path = passname.split('/')
        category, label, login = path[0], path[1], path[2]
        for key, item in self.items[category].items():
            if item['label'] == label and item['login'] == login:
                return item['pw']

    def show_password(self, passname):
        password = self.get_password(passname)
        if self.output_to_clipboard:
            pyperclip.copy(password)
        else:
            print(password)

    def find_password(self, passname):
        for name in self.get_passnames():
            if re.search(passname, name):
                print(name)

    def insert_password(self, passname, password):
        path = passname.split('/')
        folder, label, login = path[0], path[1], path[2]
        folder_id = self.get_folder_id(folder)
        url = "{0}/add/item/{1};{2};;{3};{4}?apikey={5}"\
                .format(self.api_endpoint,
                        label,
                        password,
                        folder_id,
                        login,
                        self.api_key)
        req = requests.get(url)
        if req.status_code != 200:
            raise ValueError('Unexpected HTTP return code: {0}\n'
                             'Request body: {1}'
                             .format(req.status_code, req.text))

    def generate_password(self, passname):
        wordlist = xp.generate_wordlist(xp.locate_wordfile())
        password = xp.generate_xkcdpassword(wordlist)
        print('Generated password: "{0}"'.format(password))
        self.insert_password(passname, password)

    def search_password(self):
        passnames_completer = WordCompleter(self.get_passnames(),
                                            ignore_case=True)
        passname = prompt('Password to display: ',
                          completer=passnames_completer,
                          history=self.history,
                          auto_suggest=AutoSuggestFromHistory(),
                          enable_history_search=True,
                          complete_while_typing=True,
                          on_abort=AbortAction.RETRY)
        self.show_password(passname)

    def shell(self):
        try:
            while True:
                self.search_password()
        except EOFError:
            sys.exit(0)

    def dump(self):
        print(json.dumps(self.items, sort_keys=True, indent=4))


if __name__ == "__main__":
    arguments = docopt(__doc__)
    config_path = expanduser('~/.teampass.json')

    try:
        config = json.load(open(config_path))
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        print('Unable to read config file {0}.\n'
              'Make sure that it exists and contains valid configuration.'
              .format(config_path))
        sys.exit(1)

    tc = TeampassClient(config['api_endpoint'],
                        config['api_key'],
                        config['categories'])

    if arguments['--clip']:
        tc.output_to_clipboard = True

    if arguments['list']:
        tc.list_passnames()
    elif arguments['show']:
        tc.show_password(arguments['<passname>'])
    elif arguments['find']:
        tc.find_password(arguments['<passname>'])
    elif arguments['insert']:
        tc.insert_password(arguments['<passname>'], getpass('Password:'))
    elif arguments['generate']:
        tc.generate_password(arguments['<passname>'])
    elif arguments['shell']:
        tc.shell()
    elif arguments['dump']:
        tc.dump()
