import os
from temp import Shell, launch_process


def set_config(reporter, app, payload):
    # TODO: get rid of drc, "with open()" should work with full path to file
    drc = app.webhook_path + '/' + app.webhook_name
    pth = app.webhook_path + '/' + app.webhook_name + '/config_app.py'
    try:
        if os.path.isfile(pth):
            # TODO: save previous configuration to restore if fail
            os.remove(pth)

        with open(os.path.join(drc, 'config_app.py'), "wb") as f:
            f.write(str.encode(payload))

        if os.path.isfile(pth):
            reporter('Config file was successfully created (updated)!')
            app.cfg = app.init_config(app.cfg)
            if app.cfg is not False:  # TODO: Remake
                reporter('Config file was successfully imported, there are its params: %s, %s' % (app.domain, app.port))
            else:
                reporter('Error importing config file')
        else:
            reporter('No file')
    except Exception as e:
        reporter(e)


def get_config(reporter, app):

    if not os.path.isfile(app.webhook_path + '/' + app.webhook_name + '/config_app.py'):
        reporter('There is no env file in the application folder')

    try:
        with open(os.path.join(app.webhook_path + '/' + app.webhook_name, 'config_app.py'), "rb") as f:
            config_content = f.read()
        reporter(config_content)
    except Exception as e:
        reporter(e)


def init(reporter, app, payload=None):
    # TODO: Check status
    # TODO: Clear everything, if exists
    # TODO: Validate env file
    # TODO: Insert clearing of images, volumes and networks

    sh = Shell(reporter)

    try:
        sh.execute([{'cmd': 'sudo mkdir ' + app.path + '/' + app.name},
                    {'cmd': 'sudo chmod -R 777 ' + app.path + '/' + app.name},
                    {'cmd': 'sudo -u ' + app.username + ' git clone --branch ' + app.github_branchname +
                            ' --single-branch ' + app.github + ' ' + app.path + '/' + app.name}])

        if payload is not None:
            reporter('Prepare to save .env file to the %s/%s folder' % (app.path, app.name))
            # with open(os.path.join(app.path + '/' + app.name, app.env), "wb") as f:
            #     f.write(str.encode(payload))
            #     reporter('File %s/%s/%s saved' % (app.path, app.name, app.env))

            with open(app.webhook_path + '/' + app.webhook_name + '/' + app.env, "wb") as f:
                f.write(str.encode(payload))
                reporter('File %s/%s/%s saved' % (app.webhook_path, app.webhook_name, app.env))

        sh.execute([{'cmd': 'sudo mv ' + app.webhook_path + '/' + app.webhook_name + '/' + app.env +
                            ' ' + app.path + '/' + app.name}])

        res = launch_process(reporter,
                             {'cmd': 'sudo docker-compose -f ' + app.path + '/' + app.name + '/docker-compose.yml up',
                              'contain': app.success_phrase})

        # TODO: get rid of duplication commands

        if res:
            reporter('Service launched at port: ' + str(app.port))
        else:
            reporter('Fail to launch service at port: ' + str(app.port))
            return

        apache_conf_file = ''
        rewrite_part = '''RewriteEngine On\n\
            RewriteCond %{HTTPS} !on\n\
            RewriteRule (.*) https://%{HTTP_HOST}%{REQUEST_URI}'''

        reporter('app.ssl: ' + str(app.ssl))
        if app.ssl:
            apache_conf_file = '''<VirtualHost *:80>
    ServerName %(domain)s
    ServerAlias %(domain)s
    <Location />
        Order allow,deny
        Allow from all
        Require all granted
    </Location>
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:%(port)s/
    ProxyPassReverse / http://127.0.0.1:%(port)s/
    %(rw)s
</VirtualHost>

<VirtualHost *:443>
    SSLEngine on
    SSLCertificateFile %(ssl_path)s/%(app_name)s/certificate.crt
    SSLCertificateKeyFile %(ssl_path)s/%(app_name)s/private.key
    SSLCertificateChainFile %(ssl_path)s/%(app_name)s/certificate_ca.crt

    ServerName %(domain)s
    ServerAlias %(domain)s
    <Location />
        Order allow,deny
        Allow from all
        Require all granted
    </Location>
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:%(port)s/
    ProxyPassReverse / http://127.0.0.1:%(port)s/
</VirtualHost>''' % {'rw': rewrite_part, 'domain': app.domain, 'port': str(app.port), 'ssl_path': app.ssl_path,
                     'app_name': app.name}
        else:
            apache_conf_file = '''<VirtualHost *:80>
    ServerName %s
    ServerAlias %s
    <Location />
        Order allow,deny
        Allow from all
        Require all granted
    </Location>
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:%s/
    ProxyPassReverse / http://127.0.0.1:%s/
</VirtualHost>''' % (app.domain, app.domain, str(app.port), str(app.port))

        with open(os.path.join('%s/%s' % (app.path, app.name), app.domain + '.conf'), "wb") as fp:
            fp.write(str.encode(apache_conf_file))
            reporter('File %s/%s/%s.conf saved' % (app.path, app.name, app.domain))

        # Here should be check for saving file

        sh.execute([{'cmd': 'sudo mv ' + app.path + '/' + app.name + '/' + app.domain +
                            '.conf /etc/apache2/sites-available'},
                    {'cmd': 'sudo a2ensite ' + app.domain + '.conf'}])

        sh.execute([{'cmd': 'echo "' + app.userpass + '" | sudo service apache2 reload'}])
        sh.execute([{'cmd': 'sudo service apache2 reload'}])

    except Exception as e:
        reporter('RESULT: FAIL')
        reporter(str({'exception': str(e.__class__),
                      'attrs': str(e.__dict__),
                      'message': str(e.__repr__())}))


def init_ping(reporter, app):

    sh = Shell(reporter)

    try:
        sh.execute([{'cmd': 'sudo mkdir ' + app.path + '/ping'},
                    {'cmd': 'sudo chmod -R 777 ' + app.path + '/ping'}])

        index_file = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>Ping...</title>
</head>
<body>
    <h1>Ping...</h1>
</body>
</html>'''

        with open('%s/%s/index.html' % (app.webhook_path, app.webhook_name), "wb") as fp:
            fp.write(str.encode(index_file))
            reporter('File %s/%s/index.html saved' % (app.webhook_path, app.webhook_name))

        sh.execute([{'cmd': 'sudo mv ' + app.webhook_path + '/' + app.webhook_name + '/index.html ' + app.path + '/ping'}])

        apache_conf_file = '''<VirtualHost *:80>
    ServerName %(domain)s
    ServerAlias %(domain)s
    DocumentRoot %(app_path)s/ping
    <Directory %(app_path)s/ping/>
            Options FollowSymLinks
            AllowOverride None
            Require all granted
    </Directory>
    ErrorLog %(app_path)s/ping/error.log
    CustomLog %(app_path)s/ping/access.log combined
</VirtualHost>''' % {'domain': app.domain, 'app_path': app.path}

        with open('%s/%s/%s.conf' % (app.webhook_path, app.webhook_name, app.domain), "wb") as fp:
            fp.write(str.encode(apache_conf_file))
            reporter('File %s/%s/%s.conf saved' % (app.webhook_path, app.webhook_name, app.domain))

        # Here should be check for saving file

        sh.execute([{'cmd': 'sudo mv ' + app.webhook_path + '/' + app.webhook_name + '/' + app.domain +
                            '.conf /etc/apache2/sites-available'},
                    {'cmd': 'sudo a2ensite ' + app.domain + '.conf'}])

        sh.execute([{'cmd': 'echo "' + app.userpass + '" | sudo service apache2 reload'}])
        sh.execute([{'cmd': 'sudo service apache2 reload'}])

    except Exception as e:
        reporter('RESULT: FAIL')
        reporter(str({'exception': str(e.__class__),
                      'attrs': str(e.__dict__),
                      'message': str(e.__repr__())}))


def kill_ping(reporter, app):

    sh = Shell(reporter)

    sh.execute([
        {'force': True, 'cmd': 'sudo a2dissite %s.conf' % app.domain},
        {'force': True, 'cmd': 'sudo rm -v /etc/apache2/sites-available/%s.conf' % app.domain},
        {'force': True, 'cmd': 'sudo rm -v %s/ping/index.html' % app.path},
        {'force': True, 'cmd': 'sudo rm -r %s/ping' % app.path},
        {'force': True, 'cmd': 'sudo service apache2 reload'},
    ])


def kill(reporter, app):

    # TODO: Check status ???? Should kill anyway
    # TODO: Clear everything, if exists

    sh = Shell(reporter)
    dc_file = 'docker-compose.yml'

    sh.execute([
        {'force': True, 'cmd': 'sudo a2dissite %s.conf' % app.domain},
        {'force': True, 'cmd': 'sudo rm -v /etc/apache2/sites-available/%s.conf' % app.domain},
        {'force': True, 'cmd': 'sudo docker-compose -f %s/%s/%s down' % (app.path, app.name, dc_file)},
        {'force': True, 'cmd': 'sudo rm -r %s/%s' % (app.path, app.name)},
        {'force': True, 'cmd': 'echo "y" | sudo docker system prune'},
        # {'force': True, 'cmd': 'echo "' + app.userpass + '" | sudo service apache2 reload'},
        {'force': True, 'cmd': 'sudo service apache2 reload'},
    ])


def set_env(reporter, app, payload):

    try:
        with open(os.path.join(app.path + '/' + app.name, app.env), "wb") as fl:
            fl.write(str.encode(payload))
        reporter('File with environment variables was successfully created (updated)!')
    except Exception as e:
        reporter(e)


def get_env(reporter, app):

    if not os.path.isdir(app.path + '/' + app.name):
        # TODO: Place here a RESTfull error
        reporter('There is no folder for the application, probably\
        the application wasn\'t installed at all on the server')

    if not os.path.isfile(app.path + '/' + app.name + '/' + app.env):
        # TODO: Place here a RESTfull error
        reporter('There is no env file in the application folder')

    try:
        with open(os.path.join(app.path + '/' + app.name, app.env), "rb") as reader:
            env_content = reader.read()
        reporter(env_content)
    except Exception as e:
        reporter(e)


def reload(reporter, app):

    # TODO: Check status
    # TODO: If not appropriate status (should be «running»), raise an error.

    sh = Shell(reporter)

    sh.execute([{'cmd': 'sudo docker-compose -f ' + app.path + '/' + app.name + '/docker-compose.yml down'}])
    res = launch_process(reporter,
                         {'cmd': 'sudo docker-compose -f ' + app.path + '/' + app.name + '/docker-compose.yml up',
                          'contain': app.success_phrase})
    if res:
        reporter('Service launched at port: ' + str(app.port))
    else:
        reporter('Fail to launch service at port: ' + str(app.port))


def deploy(reporter, app):

    # TODO: Check status
    # TODO: If not appropriate status (should be «running»), raise an error.

    sh = Shell(reporter)
    sh.execute([{'cmd': 'sudo docker-compose -f ' + app.path + '/' + app.name + '/docker-compose.yml down'},
                {'cmd': 'sudo -u ' + app.username + ' git -C ' + app.path + '/' + app.name +
                        ' pull origin ' + app.github_branchname}])
    res = launch_process(reporter,
                         {'cmd': 'sudo docker-compose -f ' + app.path + '/' + app.name + '/docker-compose.yml up',
                          'contain': app.success_phrase})
    if res:
        reporter('Service launched at port: ' + str(app.port))
    else:
        reporter('Fail to launch service at port: ' + str(app.port))


def cmd(reporter, command):
    sh = Shell(reporter)
    sh.execute([{'force': True, 'cmd': command}])
    return


def cmdp(reporter, command):
    res = launch_process(reporter,
                         {'cmd': command,
                          'contain': 'abracadabra'})
    reporter('THE END. RES: ' + str(type(res)))
    return


def save_ssl_file(reporter, app, file_name, file):
    sh = Shell(reporter)
    pth = app.webhook_path + '/' + app.webhook_name + '/' + file_name
    with open(pth, 'wb') as new_file:
        new_file.write(file)
    reporter('File save to the Webhook folder')

    if os.path.isfile(app.ssl_path + '/' + app.name + '/' + file_name):
        reporter('In the target folder the same file was found')
        # TODO: save previous configuration to restore if fail
        os.remove(app.ssl_path + '/' + app.name + '/' + file_name)
        sh.execute([
            # {'cmd': 'sudo rm -v %s/%s' % (app.app.ssl_path, file_name)},
            {'cmd': 'sudo mv %s/%s/%s %s/%s' % (app.webhook_path, app.webhook_name, file_name, app.ssl_path, app.name)},
        ])
        reporter('There was another %s file, it was rewrited' % file_name)
    else:
        reporter('File doesn\'t exist')
        if not os.path.isdir(app.ssl_path + '/' + app.name):
            sh.execute([
                {'cmd': 'sudo mkdir ' + app.ssl_path + '/' + app.name},
                {'cmd': 'sudo chmod -R 777 ' + app.ssl_path + '/' + app.name},
            ])

        sh.execute([
            {'cmd': 'sudo mv %s/%s/%s %s/%s' % (app.webhook_path, app.webhook_name, file_name, app.ssl_path, app.name)},
        ])

    reporter('Success')


def remove_ssl_files(reporter, app, file_names):
    for file_name in file_names:
        pth = '%s/%s/%s' % (app.ssl_path, app.name, file_name)
        if os.path.isfile(pth):
            reporter('File "%s" was found in %s/%s folder...' % (file_name, app.ssl_path, app.name))
            os.remove(pth)
            reporter('Removed!')

    reporter('DONE')


def remove_config_file(reporter, app, file_name):
    pth = '%s/%s/%s' % (app.webhook_path, app.webhook_name, file_name)
    if os.path.isfile(pth):
        reporter('File "%s" was found in %s/%s folder...' % (file_name, app.webhook_path, app.webhook_name))
        os.remove(pth)
        reporter('Removed!')
    else:
        reporter('File "%s" wasn\'t found in %s/%s folder...' % (file_name, app.webhook_path, app.webhook_name))
        os.remove(pth)

    reporter('DONE')


def update(reporter, app):

    sh = Shell(reporter)

    try:
        sh.execute([{'cmd': 'sudo -u ' + app.username + ' git -C ' + app.webhook_path + '/' + app.webhook_name + ' pull'},
                    {'cmd': 'echo "' + app.userpass + '" | sudo service apache2 reload'},
                    {'cmd': 'sudo service apache2 reload'}])

    except Exception as e:
        reporter('RESULT: FAIL')
        reporter(str({'exception': str(e.__class__),
                      'attrs': str(e.__dict__),
                      'message': str(e.__repr__())}))


def ping(app):
    greetings = '''Hello, I\'m Webhook (version %s)
You can use those commands:

/start — returns list of commands
/set_config — creates config file for app from the text under the command
/get_config — returns config file for app
/rm_config — remove config file for app
/init — deploy the application from scratch
/kill — liquidate application completely
/get_status — not ready!
/reload — down and up docker-compose
/deploy — reload + git pull
/get_env — returns text of env file
/set_env — add / update env file from the message text (starts from 2nd line)
/start_server — not ready!
/stop_server — not ready!
/set_blocked — not ready!
/update — updates webhook to the latest version (may cause errors)

To upload certificate files just send them to the telegram bot: certificate.crt, certificate_ca.crt, private.key

%s''' % (app.version, 'Config file WASN\'T SET!' if app.cfg is None else 'Config file WAS SET!')
    return greetings

