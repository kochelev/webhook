# TODO: rollback when there is any error
# TODO: make response readable
# TODO: create method «get status»
# TODO: create method «start server»
# TODO: create method «stop server»
# TODO: create method «change domain»
# TODO: block no master user, who tries DDoS, in the telegram
# TODO: ask confirmation before each critical operation
# TODO: add a role model for different types of users
# TODO: make authorization as a stand alone function

# TODO: add function "get_status":
#       Check if repository downloaded
#       Check if git is updated
#       Check if env file was set
#       Check if docker container is running
#       Check if curl can access docker container
#       Check if apache site enabled
#       Check if web service works well

# git -C /home/{USER}/{FOLDER} pull
# sudo service apache2 reload

import os
import hmac
import importlib
from hashlib import sha256
from flask import Flask, jsonify, request, send_from_directory
from threading import Thread
import telebot
from scripts import set_config, get_config, init, kill, get_env, set_env, \
    reload, deploy, cmd, cmdp, ping, save_ssl_file, remove_ssl_files, remove_config_file, update, \
    init_ping, kill_ping
import config_wh

app = Flask(__name__)

app.version = '1.1.016'
app.env = '.env'

# WEBHOOK CONSTANTS:

app.dbg = config_wh.env == 'dev'
app.username = config_wh.user_name
app.userpass = config_wh.user_pass
app.webhook_domain = config_wh.webhook_domain
app.webhook_path = config_wh.webhook_path
app.webhook_name = config_wh.webhook_name
app.path = config_wh.app_path
app.name = config_wh.app_name
app.telegram_bot_key = config_wh.telegram_bot_key
app.telegram_master_id = config_wh.telegram_master_id
app.ssl_path = config_wh.ssl_path

# CONFIG CONSTANTS:

# TODO: create decorator that checks if app config parameters were set?


def init_config(has_config=False):
    try:
        # TODO: get rid of assigning module to the app object!
        if has_config is True:
            # TODO: put a correct check for loaded module
            importlib.reload(app.config_app)
        else:
            app.config_app = importlib.import_module('config_app')

        app.github = app.config_app.app_ssh_github_link
        app.github_branchname = app.config_app.app_github_branchname
        app.secret_key = app.config_app.github_secret_key
        app.port = app.config_app.app_docker_port
        app.success_phrase = app.config_app.app_docker_success_phrase
        app.domain = app.config_app.app_domain
        app.ssl = app.config_app.app_ssl

        return True
    except Exception as e:  # NameError
        print(e.__class__)
        print(e.__repr__())
        return False


app.init_config = init_config
app.cfg = app.init_config()


app.no_cfg_message = '''github_secret_key = 'secret'
app_ssh_github_link = 'SSH link to the application GitHub repository'
app_docker_port = 'port where the container works, as a number'
app_docker_success_phrase = 'phrase which indicates that container successfully started'
app_domain = 'domain name for the application, format: "domain.com"'
app_ssl = True / False'''

bot = telebot.TeleBot(app.telegram_bot_key)
bot.set_webhook(url=app.webhook_domain)


@app.route('/', methods=["GET"])
def index():
    return "Hello, I\'m Webhook, version %s" % app.version


@app.route('/', methods=["POST"])
def webhook():

    header_github_signature = None
    event_type = None
    try:
        # TODO: remake this part
        header_github_signature = request.headers['X-Hub-Signature-256']
        event_type = request.headers.get('X-GitHub-Event')
    except KeyError as e:
        # TODO: check if this is a telegram message
        # TODO: get rid of that telebot messages proxy hack
        bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
        return 'OK'

    sha_name, github_signature = header_github_signature.split('=')
    hashhex = hmac.new(str.encode(app.secret_key), request.data, digestmod='sha256').hexdigest()

    if not hmac.compare_digest(hashhex, github_signature):
        return 'Wrong GitHub secret', 403

    if event_type == 'ping':
        return ping(app)
        # TODO: clarify what are this actions in GitHub for
    elif event_type == 'release':
        if request.json['action'] == 'published':
            if app.cfg is None:
                return 'Application deploy configuration should \
                be set, use Telegram command /set_config with text for config file from new line\n%s'\
                       % app.no_cfg_message, 500

            bot.send_message(app.telegram_master_id, 'GitHub requested for deploy! Accepted!')
            Thread(
                target=lambda: deploy(
                    lambda text: bot.send_message(app.telegram_master_id, text),
                    app
                )
            ).start()
            return 'GitHub requested for deploy! Accepted!'
        else:
            return
    else:
        return 'GitHub requested, but not supported event type "%s"!' % event_type, 400


@bot.message_handler(commands=['set_config'])
def set_config_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /set_config!')
        bot.send_message(app.telegram_master_id, message)
        return

    # TODO: paste question here, if there is a config file on the server, should it be rewrited?
    # TODO: validate parameters of config

    config_content = message.text[len('set_config') + 2:]
    if len(config_content) == 0:
        bot.send_message(app.telegram_master_id, '''Nothing was sent!
Write config file parameters under the "/set_config" line.
Use "Shift+Enter" to start a new line!''')
        return
    set_config(lambda text: bot.send_message(message.from_user.id, text), app, config_content)


@bot.message_handler(commands=['get_config'])
def get_config_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /get_env!')
        bot.send_message(app.telegram_master_id, message)
        return

    if app.cfg is None:
        bot.send_message(app.telegram_master_id, 'Application deploy configuration should be set, \
                                                 use command /set_config with text from new line')
        bot.send_message(app.telegram_master_id, app.no_cfg_message)
        return

    get_config(lambda text: bot.send_message(app.telegram_master_id, text), app)


@bot.message_handler(commands=['rm_config'])
def remove_config_file_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /start!')
        bot.send_message(app.telegram_master_id, message)
        return

    file_name = 'config_app.py'
    remove_config_file(lambda text: bot.send_message(app.telegram_master_id, text), app, file_name)


@bot.message_handler(commands=['init'])
def init_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /init!')
        bot.send_message(app.telegram_master_id, message)
        return

    # if hasattr(app.app_github_ssh_link):  #app.cfg is None:
    #     bot.send_message(app.telegram_master_id, 'Application deploy configuration should be set, \
    #                                              use command /set_config with text from new line')
    #     bot.send_message(app.telegram_master_id, app.no_cfg_message)
    #     return

    bot.send_message(message.from_user.id, 'Master requested for initialization! Accepted!')
    env_content = message.text[len('init') + 2:]
    if len(env_content) == 0:
        env_content = None
    init(lambda text: bot.send_message(message.from_user.id, text), app, env_content)


@bot.message_handler(commands=['init_ping'])
def init_ping_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /init!')
        bot.send_message(app.telegram_master_id, message)
        return

    bot.send_message(message.from_user.id, 'Master requested for initialization of PING page! Accepted!')
    init_ping(lambda text: bot.send_message(message.from_user.id, text), app)


@bot.message_handler(commands=['kill_ping'])
def kill_ping_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /init!')
        bot.send_message(app.telegram_master_id, message)
        return

    bot.send_message(message.from_user.id, 'Master requested for killing of the PING page! Accepted!')
    kill_ping(lambda text: bot.send_message(message.from_user.id, text), app)


@bot.message_handler(commands=['deploy'])
def deploy_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /deploy!')
        bot.send_message(app.telegram_master_id, message)
        return

    if app.cfg is None:
        bot.send_message(app.telegram_master_id, 'Application deploy configuration should be set, \
                                                 use command /set_config with text from new line')
        bot.send_message(app.telegram_master_id, app.no_cfg_message)
        return

    bot.send_message(app.telegram_master_id, 'Master requested for deploy! Accepted!')
    deploy(lambda text: bot.send_message(app.telegram_master_id, text), app)


@bot.message_handler(commands=['reload'])
def reload_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /reload!')
        bot.send_message(app.telegram_master_id, message)
        return

    if app.cfg is None:
        bot.send_message(app.telegram_master_id, 'Application deploy configuration should be set, \
                                                 use command /set_config with text from new line')
        bot.send_message(app.telegram_master_id, app.no_cfg_message)
        return

    bot.send_message(app.telegram_master_id, 'Master requested for reload! Accepted!')
    reload(lambda text: bot.send_message(app.telegram_master_id, text), app)


@bot.message_handler(commands=['kill'])
def kill_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /kill!')
        bot.send_message(app.telegram_master_id, message)
        return

    if app.cfg is None:
        bot.send_message(app.telegram_master_id, 'Application deploy configuration should be set, \
                                                 use command /set_config with text from new line')
        bot.send_message(app.telegram_master_id, app.no_cfg_message)
        return

    bot.send_message(message.from_user.id, 'Master requested for liquidation! Accepted!')
    kill(lambda text: bot.send_message(message.from_user.id, text), app)


@bot.message_handler(commands=['set_env'])
def set_env_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /set_env!')
        bot.send_message(app.telegram_master_id, message)
        return

    if app.cfg is None:
        bot.send_message(app.telegram_master_id, 'Application deploy configuration should be set, \
                                                 use command /set_config with text from new line')
        bot.send_message(app.telegram_master_id, app.no_cfg_message)
        return

    env_content = message.text[len('set_env') + 2:]
    if len(env_content) == 0:
        bot.send_message(app.telegram_master_id,
                         '''Nothing was sent!
                            Write environment variables under the "/set_env" line.
                            Use "Shift+Enter" to start a new line!''')
        return

    set_env(lambda text: bot.send_message(app.telegram_master_id, text), app, env_content)


@bot.message_handler(commands=['get_env'])
def get_env_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /get_env!')
        bot.send_message(app.telegram_master_id, message)
        return

    if app.cfg is None:
        bot.send_message(app.telegram_master_id, 'Application deploy configuration should be set, \
                                                 use command /set_config with text from new line')
        bot.send_message(app.telegram_master_id, app.no_cfg_message)
        return

    get_env(lambda text: bot.send_message(app.telegram_master_id, text), app)


@bot.message_handler(commands=['cmd'])
def cmd_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /exec!')
        bot.send_message(app.telegram_master_id, message)
        return

    command = message.text[len('cmd') + 2:]
    if len(command) == 0:
        bot.send_message(app.telegram_master_id,
                         '''Nothing was sent!
                            Write command under the "/cmd" line.
                            Use "Shift+Enter" to start a new line!''')
        return

    cmd(lambda text: bot.send_message(app.telegram_master_id, text), command)


@bot.message_handler(commands=['cmdp'])
def cmdp_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /exec!')
        bot.send_message(app.telegram_master_id, message)
        return

    command = message.text[len('cmdp') + 1:]
    if len(command) == 0:
        bot.send_message(app.telegram_master_id,
                         '''Nothing was sent!'
                            Write command after the "/cmdp" with one space!''')
        return

    cmdp(lambda text: bot.send_message(app.telegram_master_id, text), command)


@bot.message_handler(content_types=['document'])
def upload(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /start!')
        bot.send_message(app.telegram_master_id, message)
        return

    file_name = message.document.file_name
    names = ['certificate.crt', 'certificate_ca.crt', 'private.key']
    if file_name not in names:
        bot.reply_to(message, '''Not appropriate file name!
Should be "certificate.crt", "certificate_ca.crt" or "private.key"''')
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    save_ssl_file(lambda text: bot.send_message(app.telegram_master_id, text), app, file_name, downloaded_file)


@bot.message_handler(commands=['rm_ssl'])
def remove_ssl_files_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /start!')
        bot.send_message(app.telegram_master_id, message)
        return

    names = ['certificate.crt', 'certificate_ca.crt', 'private.key']
    remove_ssl_files(lambda text: bot.send_message(app.telegram_master_id, text), app, names)


@bot.message_handler(commands=['update'])
def update_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /start!')
        bot.send_message(app.telegram_master_id, message)
        return

    update(lambda text: bot.send_message(app.telegram_master_id, text), app)


@bot.message_handler(commands=['start'])
def ping_method(message):
    if str(message.from_user.id) != str(app.telegram_master_id):
        bot.send_message(app.telegram_master_id, 'ATTENTION! Somebody tries to /start!')
        bot.send_message(app.telegram_master_id, message)
        return

    bot.send_message(app.telegram_master_id, ping(app))
    # bot.send_message(message.chat.id, ping(app))
    # bot.send_message(message.chat.id, message)


@bot.message_handler()
def other(message):
    if not app.dbg:
        return

    bot.send_message(message.chat.id, message)
    bot.reply_to(message, message)


if __name__ == '__main__':
    app.run()
