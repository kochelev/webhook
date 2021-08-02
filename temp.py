import subprocess
import shlex
import sys
import codecs


class Shell:

    def __init__(self, reporter):
        self.reporter = reporter

    def execute(self, script):
        self.reporter('--> SCRIPT STARTED')

        for line in script:
            self.reporter('CMD: ' + str(line))
            if 'force' in line and line['force']:
                try:
                    response = subprocess.check_output(shlex.split(line['cmd']))
                    if len(response) > 0:
                        x = ''
                        try:
                            x = str(response)
                        except UnicodeDecodeError:
                            x = 'UnicodeDecodeError'
                        self.reporter('SUCCESS\n%s' % x)
                    else:
                        self.reporter('SUCCESS')
                except Exception as e:
                    self.reporter('FAIL: %s' % str({'exception': str(e.__class__),
                                                    'attrs': str(e.__dict__),
                                                    'message': str(e.__repr__())}))
                    continue
            else:
                try:
                    response = subprocess.check_output(shlex.split(line['cmd']))
                    if len(response) > 0:
                        self.reporter('SUCCESS: %s' % str(response))
                    else:
                        self.reporter('SUCCESS')
                except Exception as e:
                    self.reporter('FAIL: %s' % str({'exception': str(e.__class__),
                                                    'attrs': str(e.__dict__),
                                                    'message': str(e.__repr__())}))
                    self.reporter('SCRIPT ABORTED')
                    break

        self.reporter('<-- SCRIPT FINISHED')


def execute(reporter, cmd):

    ppn = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, universal_newlines=True)

    reporter('PPN.STDOUT: ' + str(ppn.stdout))
    logs = iter(ppn.stdout.readline, '')
    # TODO: UGLY BUG WITH ANSCII ENCODING FOR REACT APPLICATION
    while True:
        try:
            stdout_line = next(logs)
        except UnicodeDecodeError:
            yield 'CONTINUE'

        yield stdout_line

    # try:
    #     for stdout_line in iter(ppn.stdout.readline, ''):
    #         # reporter('cococ: ' + stdout_line.decode('utf-8', 'ignore'))
    #         yield stdout_line
    # except UnicodeDecodeError as e:
    #     reporter('UnicodeDecodeError')
    #     reporter('PSEUDO FAIL: %s' % str({'exception': str(e.__class__),
    #                                       'attrs': str(e.__dict__),
    #                                       'message': str(e.__repr__())}))
    #     reporter('CONTINUE')
    #     ppn.stdout.pop()
    #     yield 'CONTINUE'

    ppn.stdout.close()
    return_code = ppn.wait()
    if return_code:
        reporter(str(subprocess.CalledProcessError(return_code, cmd)))
        raise subprocess.CalledProcessError(return_code, cmd)

        return True


def launch_process(reporter, cmd_obj):
    reporter('--> PROCESS STARTED')
    reporter('CMD: ' + str(cmd_obj))
    # sys.stdout = codecs.getwriter("UTF-8")(sys.stdout.detach())
    if 'cmd' not in cmd_obj:
        reporter('RESULT: FAIL')
        reporter('Should have "cmd" parameter')

    if 'contain' not in cmd_obj:
        reporter('RESULT: FAIL')
        reporter('Should have "contain" parameter')

    try:

        for x in execute(reporter, cmd_obj['cmd']):
            reporter(str(x))
            if cmd_obj['contain'] in str(x):
                reporter('<-- PROCESS LAUNCHED')
                return True

        reporter('FINISHED WITHOUT EXCEPTIONS')

    except Exception:
        raise

    reporter('??????')
    return False
