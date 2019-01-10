import abc
import os.path
import random
import re
import string
import time
from typing import Any, Callable, Iterator, Dict, List, Optional
import webbrowser

from google.auth import credentials

from django_cloud_deploy import workflow
from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt_new
from django_cloud_deploy.cloudlib import auth
from django_cloud_deploy.cloudlib import billing
from django_cloud_deploy.cloudlib import project
from django_cloud_deploy.skeleton import utils


class TemplatePromptManager(object):
    """Used as a base template for all Prompt Managers interacting with user.

    They should all have prompt method that should make subsequent prompt calls.
    Manager should own only one parameter, for which they should have a
    validate function for which they will call if the argument is already
    supplied. They also handle any busines logic related to a prompt, as well
    as become instantiated with any API related classes.

    """

    # Parameter Manager Owns must be set
    PARAMETER = None

    def __init__(self, console: io.IO, step: str, args):
        self.console = console
        self.step = step
        self.args = args

    def prompt(self) -> None:
        pass

    def validate(self, val: Any) -> bool:
        return True

    def get_credentials(self):
        return self.args.get('credentials', None)

    def _is_valid_passed_arg(self) -> bool:
        value = self.args.get(self.PARAMETER, None)
        if value is None:
            return False

        try:
            if self.validate(value):
                msg = '{} {}: {}'.format(self.step, self.PARAMETER, value)
                self.console.tell(msg)
                return True
        except ValueError as e:
            self.console.error(e)
            return False

        return False


class StringTemplatePromptManager(TemplatePromptManager):
    """Template for a simple string Prompt Manager."""

    PARAMETER = ''
    PARAMTER_PRETTY = ''
    DEFAULT_VALUE = ''
    BASE_MESSAGE = '{} Enter a value for {} or leave blank to use'
    DEFAUlT_MESSAGE = '[{}]: '

    def _generate_name_prompt(self):
        base_message = self.BASE_MESSAGE.format(self.step, self.PARAMTER_PRETTY)
        default_message = self.DEFAUlT_MESSAGE.format(self.DEFAULT_VALUE)
        msg = '\n'.join([base_message, default_message])
        return prompt_new.AskPrompt(
            msg, self.console, self.validate, default=self.DEFAULT_VALUE)

    def prompt(self):
        if self._is_valid_passed_arg():
            return

        self.args[self.PARAMETER] = self._generate_name_prompt().prompt()


class GoogleProjectNameManager(TemplatePromptManager):

    PARAMETER = 'project_name'

    def __init__(self,
                 console: io.IO,
                 step: str,
                 args,
                 project_client: Optional[project.ProjectClient] = None):
        super().__init__(console, step, args)
        creds = self.get_credentials()
        self.project_client = (project_client or
                               project.ProjectClient.from_credentials(creds))

    def validate(self, s: str) -> bool:
        """Validates that a string is a valid project name.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not (4 <= len(s) <= 30):
            raise ValueError(
                ('Invalid Google Cloud Platform project name "{}": '
                 'must be between 4 and 30 characters').format(s))

        if self._is_new_project():
            return True

        project_id = self.args.get('project_id', None)
        if project_id is None:
            raise ValueError('Project Id must be set')

        project_name = self.project_client.get_project(project_id)['name']
        if project_name != s:
            raise ValueError('Wrong project name given for project id.')

        return True

    def _generate_name_prompt(self):
        default_answer = 'Django Project'
        msg_base = ('{} Enter a Google Cloud Platform project name, or leave '
                    'blank to use').format(self.step)
        msg_default = '[{}]: '.format(default_answer)
        msg = '\n'.join([msg_base, msg_default])
        return prompt_new.AskPrompt(
            msg, self.console, self.validate, default=default_answer)

    def _is_new_project(self):
        must_exist = workflow.ProjectCreationMode.MUST_EXIST
        return self.args.get('project_creation_mode', None) != must_exist

    def _handle_existing_project(self):
        assert 'project_id' in self.args, 'project_id must be set'
        project_id = self.args['project_id']
        project_name = self.project_client.get_project(project_id)['name']
        message = '{} {}: {}'.format(self.step, self.PARAMETER, project_name)
        self.console.tell(message)
        self.args['project_name'] = project_name

    def prompt(self):
        if self._is_valid_passed_arg():
            return

        if self._is_new_project():
            self.args['project_name'] = self._generate_name_prompt().prompt()
        else:
            self._handle_existing_project()


class GoogleNewProjectIdManager(TemplatePromptManager):

    PARAMETER = 'project_id'

    def __init__(
            self,
            console: io.IO,
            step: str,
            args,
    ):
        super().__init__(console, step, args)

    def validate(self, s: str):
        """Validates that a string is a valid project id.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not re.match(r'[a-z][a-z0-9\-]{5,29}', s):
            raise ValueError(('Invalid Google Cloud Platform Project ID "{}": '
                              'must be between 6 and 30 characters and contain '
                              'lowercase letters, digits or hyphens').format(s))

    def _generate_default_project_id(self, project_name=None):
        default_project_id = (project_name or 'django').lower()
        default_project_id = default_project_id.replace(' ', '-')
        if default_project_id[0] not in string.ascii_lowercase:
            default_project_id = 'django-' + default_project_id
        default_project_id = re.sub(r'[^a-z0-9\-]', '', default_project_id)

        return '{0}-{1}'.format(default_project_id[0:30 - 6 - 1],
                                random.randint(100000, 1000000))

    def _generate_id_prompt(self):
        project_name = self.args.get('project_name', None)
        default_answer = self._generate_default_project_id(project_name)
        msg_base = ('{} Enter a Google Cloud Platform Project ID, '
                    'or leave blank to use').format(self.step)
        msg_default = '[{}]: '.format(default_answer)
        msg = '\n'.join([msg_base, msg_default])
        return prompt_new.AskPrompt(
            msg, self.console, self.validate, default=default_answer)

    def prompt(self):
        if self._is_valid_passed_arg():
            return

        self.args['project_id'] = self._generate_id_prompt().prompt()


class GoogleProjectIdManager(TemplatePromptManager):

    PARAMETER = 'project_id'

    def __init__(self,
                 console: io.IO,
                 step: str,
                 args,
                 project_client: project.ProjectClient = None):
        super().__init__(console, step, args)
        creds = self.get_credentials()
        self.project_client = (project_client or
                               project.ProjectClient.from_credentials(creds))

    def prompt(self):
        prompter = GoogleNewProjectIdManager(self.console, self.step, self.args)

        if self.args.get('use_existing_project', False):
            prompter = GoogleExistingProjectIdManager(
                self.console, self.step, self.args, self.project_client)

        prompter.prompt()


class GoogleExistingProjectIdManager(TemplatePromptManager):

    PARAMETER = 'project_id'

    def __init__(self, console: io.IO, step: str, args,
                 project_client: project.ProjectClient):
        super().__init__(console, step, args)
        creds = self.get_credentials()
        self.project_client = (project_client or
                               project.ProjectClient.from_credentials(creds))

    def _generate_existing_id_prompt(self):
        msg = ('{} Enter the <b>existing<b> Google Cloud Platform Project ID '
               'to use.').format(self.step)
        return prompt_new.AskPrompt(msg, self.console, self.validate)

    def prompt(self):
        """Prompt the user to a Google Cloud Platform project id.

        If the user supplies the project_id as a flag we want to validate that
        it exists. We tell the user to supply a new one if it does not.

        """

        if self._is_valid_passed_arg():
            return

        self.args['project_id'] = self._generate_existing_id_prompt().prompt()

    def validate(self, s):
        """Validates that a string is a valid project id.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """

        if not re.match(r'[a-z][a-z0-9\-]{5,29}', s):
            raise ValueError(('Invalid Google Cloud Platform Project ID "{}": '
                              'must be between 6 and 30 characters and contain '
                              'lowercase letters, digits or hyphens').format(s))

        if not self.project_client.project_exists(s):
            raise ValueError('Project {} does not exist'.format(s))


class CredentialsPromptManager(TemplatePromptManager):

    PARAMETER = 'credentials'

    def __init__(self,
                 console: io.IO,
                 step: str,
                 args,
                 auth_client: Optional[auth.AuthClient] = None):
        super().__init__(console, step, args)
        self.auth_client = auth_client or auth.AuthClient()

    def _generate_credentials_prompt(self, active_account: str):
        msg = ('You have logged in with account [{}]. Do you want to '
               'use it? [Y/n]: ').format(active_account)
        return prompt_new.BinaryPrompt(msg, self.console, default='Y')

    def prompt(self):
        """Prompt the user for access to the Google credentials.

        Returns:
            The user's credentials.
        """
        if self._is_valid_passed_arg():
            return

        self.console.tell(
            ('{} In order to deploy your application, you must allow Django '
             'Deploy to access your Google account.').format(self.step))
        create_new_credentials = True
        active_account = self.auth_client.get_active_account()
        credentials_prompt = self._generate_credentials_prompt(active_account)

        if active_account:  # The user has already logged in before
            use_active_credentials = credentials_prompt.prompt().lower()
            create_new_credentials = use_active_credentials == 'n'

        if create_new_credentials:
            creds = self.auth_client.create_default_credentials()
        else:
            creds = self.auth_client.get_default_credentials()

        self.args[self.PARAMETER] = creds


class BillingPrompt(TemplatePromptManager):
    """Allow the user to select a billing account to use for deployment."""

    PARAMETER = 'billing_account_name'

    def __init__(self,
                 console: io.IO,
                 step: str,
                 args,
                 billing_client: billing.BillingClient = None):
        super().__init__(console, step, args)
        creds = self.get_credentials()
        self.billing_client = (billing_client or
                               billing.BillingClient.from_credentials(creds))

    def _get_new_billing_account(
            self, existing_billing_accounts: List[Dict[str, Any]]) -> str:
        """Ask the user to create a new billing account and return name of it.

        Args:
            existing_billing_accounts: User's billing accounts before creation
                of new accounts.

        Returns:
            Name of the user's newly created billing account.
        """
        webbrowser.open('https://console.cloud.google.com/billing/create')
        existing_billing_account_names = [
            account['name'] for account in existing_billing_accounts
        ]
        self.console.tell('Waiting for billing account to be created.')
        while True:
            billing_accounts = self.billing_client.list_billing_accounts(
                only_open_accounts=True)
            if len(existing_billing_accounts) != len(billing_accounts):
                billing_account_names = [
                    account['name'] for account in billing_accounts
                ]
                diff = list(
                    set(billing_account_names) -
                    set(existing_billing_account_names))
                return diff[0]
            time.sleep(2)

    def _does_project_exist(self) -> bool:
        must_exist = workflow.ProjectCreationMode.MUST_EXIST
        return ('project_creation_mode' in self.args and
                (self.args['project_creation_mode'] == must_exist))

    def _has_existing_billing_account(self) -> bool:
        assert 'project_id' in self.args, 'project_id must be set'
        project_id = self.args['project_id']
        billing_account = (self.billing_client.get_billing_account(project_id))
        if not billing_account.get('billingEnabled', False):
            return False

        msg = ('{} Billing is already enabled on this project.'.format(
            self.step))
        self.console.tell(msg)
        self.args[self.PARAMETER] = billing_account.get('billingAccountName')
        return True

    def _generate_billing_prompt(self, billing_accounts):
        question = ('You have the following existing billing accounts:\n{}\n'
                    'Please enter your numeric choice or press [Enter] to '
                    'create a new billing account: ')

        options = [info['displayName'] for info in billing_accounts]
        new_billing_account = ''
        return prompt_new.MultipleChoicePrompt(
            question, options, self.console, default=new_billing_account)

    def _handle_existing_billing_accounts(self, billing_accounts):
        new_billing_account = ''
        answer = self._generate_billing_prompt(billing_accounts).prompt()
        if answer == new_billing_account:
            return self._get_new_billing_account(billing_accounts)

        val = billing_accounts[int(answer) - 1]['name']
        return val

    def prompt(self):
        """Prompt the user for a billing account to use for deployment.
        """
        if self._is_valid_passed_arg():
            return

        if self._does_project_exist() and self._has_existing_billing_account():
            return

        billing_accounts = self.billing_client.list_billing_accounts(
            only_open_accounts=True)
        self.console.tell(
            ('{} In order to deploy your application, you must enable billing '
             'for your Google Cloud Project.').format(self.step))

        # If the user has existing billing accounts, we let the user pick one
        if billing_accounts:
            val = self._handle_existing_billing_accounts(billing_accounts)
            self.args[self.PARAMETER] = val
            return

        # If the user does not have existing billing accounts, we direct
        # the user to create a new one.
        self.console.tell('You do not have existing billing accounts.')
        self.console.ask('Press [Enter] to create a new billing account.')
        val = self._get_new_billing_account(billing_accounts)
        self.args[self.PARAMETER] = val

    def validate(self, s):
        """Validates that a string is a valid billing account.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """

        billing_accounts = self.billing_client.list_billing_accounts()
        billing_account_names = [
            account['name'] for account in billing_accounts
        ]
        if s not in billing_account_names:
            raise ValueError('The provided billing account does not exist.')


class PostgresPasswordPrompt(TemplatePromptManager):
    """Allow the user to enter a Django Postgres password."""

    PARAMETER = 'database_password'

    def prompt(self):
        if self._is_valid_passed_arg():
            return

        pass_prompt = prompt_new.PasswordPrompt(self.console)
        msg = 'Enter a password for the default database user "postgres"'
        self.console.tell('{} {}'.format(self.step, msg))
        self.args[self.PARAMETER] = pass_prompt.prompt()

    def validate(self, s: str):
        pass_prompt = prompt_new.PasswordPrompt(self.console)
        return pass_prompt.validate(s)


class DjangoFilesystemPath(TemplatePromptManager):
    """Allow the user to file system path for their project."""

    PARAMETER = 'django_directory_path'

    def _generate_replace_prompt(self, directory):
        msg = (('The directory \'{}\' already exists, '
                'replace it\'s contents [y/N]: ').format(directory))
        return prompt_new.AskPrompt(msg, self.console, default='n')

    def _generate_directory_prompt(self):
        base_msg = ('{} Enter a new directory path to store project source, '
                    'or leave blank to use').format(self.step)

        home_dir = os.path.expanduser('~')
        # TODO: Remove filesystem-unsafe characters. Implement a validation
        # method that checks for these.
        default_dir = os.path.join(
            home_dir,
            self.args.get('project_name', 'django-project').lower().replace(
                ' ', '-'))
        default_msg = '[{}]: '.format(default_dir)

        msg = '\n'.join([base_msg, default_msg])
        return prompt_new.AskPrompt(msg, self.console, default=default_dir)

    def prompt(self):
        """Prompt the user to enter a file system path for their project."""

        dir_prompt = self._generate_directory_prompt()
        while True:
            directory = dir_prompt.prompt()
            if os.path.exists(directory):
                replace_prompt = self._generate_replace_prompt(directory)
                if replace_prompt.prompt().lower() == 'y':
                    break

        self.args[self.PARAMETER] = directory

    def validate(self):
        # TODO
        return True


class DjangoProjectNamePrompt(StringTemplatePromptManager):
    """Allow the user to enter a Django project name."""

    PARAMETER = 'django_project_name'
    PARAMTER_PRETTY = 'Django project name'
    DEFAULT_VALUE = 'mysite'

    def validate(self, s):
        """Validates that a string is a valid Django project name.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not s.isidentifier():
            raise ValueError(('Invalid Django project name "{}": '
                              'must be a valid Python identifier').format(s))


class DjangoAppNamePrompt(StringTemplatePromptManager):
    """Allow the user to enter a Django project name."""

    PARAMETER = 'django_app_name'
    PARAMTER_PRETTY = 'Django app name'
    DEFAULT_VALUE = 'home'

    def validate(self, s):
        """Validates that a string is a valid Django project name.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not s.isidentifier():
            raise ValueError(('Invalid Django project name "{}": '
                              'must be a valid Python identifier').format(s))


class DjangoSuperuserLoginPrompt(StringTemplatePromptManager):
    """Allow the user to enter a Django superuser login."""

    PARAMETER = 'django_superuser_login'
    PARAMTER_PRETTY = 'Django superuser login name'
    DEFAULT_VALUE = 'admin'

    def validate(self, s: str):
        """Validates that a string is a valid Django superuser login.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not s.isalnum():
            raise ValueError(('Invalid Django superuser login "{}": '
                              'must be a alpha numeric').format(s))


class DjangoSuperuserPasswordPrompt(TemplatePromptManager):
    """Allow the user to enter a password for the Django superuser."""

    PARAMETER = 'django_superuser_password'

    def prompt(self):
        if self._is_valid_passed_arg():
            return

        pass_prompt = prompt_new.PasswordPrompt(self.console)
        msg = 'Enter a password for the Django superuser "{}"'.format(
            self.args['django_superuser_login'])
        self.console.tell('{} {}'.format(self.step, msg))
        self.args[self.PARAMETER] = pass_prompt.prompt()

    def validate(self, s: str):
        pass_prompt = prompt_new.PasswordPrompt(self.console)
        return pass_prompt.validate(s)


class DjangoSuperuserEmailPrompt(StringTemplatePromptManager):
    """Allow the user to enter a Django email address."""

    PARAMETER = 'django_superuser_email'
    PARAMTER_PRETTY = 'Django superuser email'
    DEFAULT_VALUE = 'test@example.com'

    def validate(self, s: str):
        """Validates that a string is a valid Django superuser email address.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not re.match(r'[^@]+@[^@]+\.[^@]+', s):
            raise ValueError(('Invalid Django superuser email address "{}": '
                              'the format should be like '
                              '"test@example.com"').format(s))


class RootPromptManager(object):
    """Class at the top level that instantiates all of the Prompt Managers."""

    PROMPT_ORDER = [
        'credentials',
        'project_id',
        'project_name',
        'billing_account_name',
        'database_password',
        'django_directory_path',
        'django_project_name',
        'django_app_name',
        'django_superuser_login',
        'django_superuser_password',
        'django_superuser_email',
    ]

    required_parameters_to_prompt = {
        'credentials': CredentialsPromptManager,
        'project_id': GoogleProjectIdManager,
        'project_name': GoogleProjectNameManager,
        'billing_account_name': BillingPrompt,
        'database_password': PostgresPasswordPrompt,
        'django_directory_path': DjangoFilesystemPath,
        'django_project_name': DjangoProjectNamePrompt,
        'django_app_name': DjangoAppNamePrompt,
        'django_superuser_login': DjangoSuperuserLoginPrompt,
        'django_superuser_password': DjangoSuperuserPasswordPrompt,
        'django_superuser_email': DjangoSuperuserEmailPrompt
    }

    def __init__(self, console: io.IO, args):
        self.console = console
        self.args = args

    def _setup(self):
        if self.args.get('use_existing_project', False):
            self.args['project_creation_mode'] = (
                workflow.ProjectCreationMode.MUST_EXIST)

    def prompt(self):
        self._setup()

        total_steps = len(self.PROMPT_ORDER)
        for i, prompt in enumerate(self.PROMPT_ORDER, 1):
            step = '<b>[{}/{}]</b>'.format(i, total_steps)
            self.required_parameters_to_prompt[prompt](self.console, step,
                                                       self.args).prompt()
