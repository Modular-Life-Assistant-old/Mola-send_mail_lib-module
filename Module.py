from core import Log

from circuits import Component, Event, handler
from email.mime.text import MIMEText
import json
import os
import smtplib


class send_mail(Event):
    def __init__(self, subject, to, msg, account=''):
        super(send_mail, self).__init__(subject, to, msg, account=account)


class Module(Component):
    channel = 'mail'
    default_account = ''
    __account_config = {}

    def add_account(self, **kwargs):
        if not 'login' in kwargs:
            Log.error('add_account as not login value')
            return

        if not self.default_account:
            self.default_account = kwargs['login']

        self.__account_config[kwargs['login']] = kwargs

    def load_configuration(self):
        dir_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'configs'
        )

        config_path = os.path.join(dir_path, 'config.json')
        if os.path.isfile(config_path):
            with open(config_path) as config_file:
                config = json.load(config_file)

                if 'default_account' in config:
                    self.default_account = config['default_account']

        accounts_path = os.path.join(dir_path, 'accounts')
        nb = 0

        if os.path.isdir(accounts_path):
            for name in os.listdir(accounts_path):
                with open(os.path.join(accounts_path, name)) as config_file:
                    self.add_account(**json.load(config_file))
                    nb += 1

        Log.info('%d account load' % nb)

    def login(self, account=''):
        config = self.__get_config(account)

        try:
            smtp_constructor_keys = ['host', 'port', 'local_hostname', \
                'timeout', 'source_address']

            smtp_kwarg = {key: config[key] for key in smtp_constructor_keys if key in config}
            conn = smtplib.SMTP(**smtp_kwarg)
            #conn.ehlo()
            #conn.starttls()

            if 'debug' in config:
                conn.set_debuglevel(config['debug'])

            if 'login' in config and 'password' in config:
                conn.login(config['login'], config['password'])

            return conn

        except smtplib.SMTPHeloError as e:
            # The server didn’t reply properly to the HELO greeting.
            Log.error('smtp hello error: %s' % str(e))

        except smtplib.SMTPAuthenticationError as e:
            # The server didn’t accept the username/password combination.
            Log.error('smtp authentication error: %s' % str(e))

        except smtplib.SMTPException as e:
            # No suitable authentication method was found.
            Log.error('smtp exception: %s' % str(e))

    @handler('send_mail', channel='*')
    def send_mail(self, subject, to, msg, account=''):
        conn = self.login(account)

        if not conn:
            return

        config = self.__get_config(account)

        if isinstance(to, str):
            to = to.replace(' ', '').split(',') if ',' in to else [to]

        mail = MIMEText(msg, 'plain')
        mail['Subject'] = subject
        mail['To'] = ', '.join(to)

        if not 'from' in config:
            config['from'] = config['login']
            
        if 'name' in config:
            mail['From'] = '%(name)s <%(from)s>' % config

        else:
            mail['From'] = config['from']

        try:
            conn.sendmail(account, to, mail.as_string())

        except smtplib.SMTPRecipientsRefused as e:
            # All recipients were refused. Nobody got the mail. The recipients attribute of the exception object is a dictionary with information about the refused recipients (like the one returned when at least one recipient was accepted).
            Log.error('smtp recipients refused: %s' % str(e))

        except smtplib.SMTPHeloError as e:
            # The server didn’t reply properly to the HELO greeting.
            Log.error('smtp hello error: %s' % str(e))

        except smtplib.SMTPSenderRefused as e:
            # The server didn’t accept the from_addr.
            Log.error('smtp sender refused: %s' % str(e))

        except smtplib.SMTPDataError as e:
            # The server replied with an unexpected error code (other than a refusal of a recipient).
            Log.error('smtp data error: %s' % str(e))

        finally:
            conn.close()

    def started(self, component):
        self.load_configuration()

    def __get_config(self, account=''):
        if not account:
            account = self.default_account

        if not account in self.__account_config:
            Log.error('smtp account "%s" unknown' % account)
            return

        return self.__account_config[account]

