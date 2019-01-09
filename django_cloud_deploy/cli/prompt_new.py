import abc
import string
from typing import List, Optional, Callable

from django_cloud_deploy.cli import io


class Prompt(object):
    """Base class for classes the collect user input from the console."""

    @abc.abstractmethod
    def prompt(self) -> str:
        """Prompt the user to enter some information.

        Returns:
            The value entered by the user.
        """
        pass

    def validate(self, s: str) -> bool:
        """Validates that a string is valid for this prompt type.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        pass


class AskPrompt(Prompt):
    """Used to ask for a single string value.

    Attributes:
        question: Question shown to the user on the console.
        console: Object to use for user I/O.
        validate: Function used to check if value provided is valid.
        default: Default value if user provides no value. (Presses enter)
    """

    def __init__(self,
                 question: str,
                 console: io.IO,
                 validate: Optional[Callable[[str], bool]] = None,
                 default: Optional[str] = None):
        self.question = question
        self.validate = validate or (lambda s: True)
        self.console = console
        self.default = default

    def prompt(self) -> str:
        """Prompt the user to enter some information.

        Returns:
            The value entered by the user.
        """
        answer = self.console.ask(self.question)
        if self.default and answer is '':
            answer = self.default
        try:
            self.validate(answer)
            return answer
        except ValueError as e:
            self.console.error(e)
            return self.prompt()


class MultipleChoicePrompt(Prompt):
    """Used to prompt user to choose from a list of values.

    Attributes:
        question: Question shown to the user on the console.
        options: Possible values user should choose from.
        console: Object to use for user I/O.
        default: Default value if user provides no value. (Presses enter)
    """

    def __init__(self,
                 question: str,
                 options: List[str],
                 console: io.IO,
                 default: Optional[str] = None):
        self.question = question
        self.options = options
        self.console = console
        self.default = default

    def prompt(self) -> str:
        """Prompt the user to choose from a list of options.

        Returns:
            The choice entered by the user.
        """
        options_formatted = [
            '{}. {}'.format(str(i), opt)
            for i, opt in enumerate(self.options, 1)
        ]
        options = '\n'.join(options_formatted)
        answer = self.console.ask(self.question.format(options))
        try:
            self.validate(answer)
            return answer
        except ValueError as e:
            self.console.error(e)
            return self.prompt()

    def validate(self, s: str):
        """Validates the option chosen is valid."""
        if self.default is not None and s == '':
            return True

        if not str.isnumeric(s):
            raise ValueError('Please enter a numeric value')

        if 1 <= int(s) <= (len(self.options) + 1):
            return True
        else:
            raise ValueError('Value is not in range')


class BinaryPrompt(Prompt):
    """Used to prompt user to choose from a yes or no question.

    Attributes:
        question: Question shown to the user on the console.
        console: Object to use for user I/O.
        default: Default value if user provides no value. (Presses enter)
    """

    def __init__(self,
                 question: str,
                 console: io.IO,
                 default: Optional[str] = None):
        self.question = question
        self.console = console
        self.default = default

    def prompt(self):
        """Prompt the user to choose from a yes or no question.

        Returns:
            The choice entered by the user.
        """
        answer = self.console.ask(self.question)
        if self.default and answer is '':
            answer = self.default
        if self.validate(answer):
            return answer
        else:
            return self.prompt()

    def validate(self, s: str):
        """Ensures value is yes or no."""
        return s.lower() in ['y', 'n']


class PasswordPrompt(Prompt):
    """Used to prompt user to choose a password field.

    Attributes:
        console: Object to use for user I/O.
    """

    def __init__(self, console: io.IO):
        self.console = console

    def prompt(self) -> str:
        """Prompt the user to enter a password.

        Returns:
            The value entered by the user.
        """
        while True:
            password1 = self.console.getpass('Password: ')
            try:
                self.validate(password1)
            except ValueError as e:
                self.console.error(e)
                continue
            password2 = self.console.getpass('Password (again): ')
            if password1 != password2:
                self.console.error('Passwords do not match, please try again')
                continue
            return password1

    def validate(self, s) -> bool:
        """Validates that a string is a valid password.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if len(s) < 5:
            raise ValueError('Passwords must be at least 6 characters long')
        allowed_characters = frozenset(string.ascii_letters + string.digits +
                                       string.punctuation)
        if frozenset(s).issuperset(allowed_characters):
            raise ValueError('Invalid character in password: '
                             'use letters, numbers and punctuation')

        return True
