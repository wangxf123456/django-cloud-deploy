# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A module defines base class for commands e.g. "new", "update"."""

import argparse
import sys
from typing import Any, Dict

from django_cloud_deploy.cli import io
import django_cloud_deploy.crash_handling


class Command(object):
    """Base class for all commands."""

    _NAME = ''
    _PROMPT_ORDER = []
    _REQUIRED_PARAMETERS_TO_PROMPT = {}

    def __init__(self, console: io.IO = io.ConsoleIO()):
        self._console = console

    @property
    def name(self):
        return self._NAME

    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser):
        """Register flags for this command.

        Subclasses should overwrite this method.

        Args:
            parser: The parser to get registered.
        """
        pass

    def _get_parameters(self,
                        args: argparse.Namespace) -> Dict[str, Any]:
        """Get necessary parameters to run the command.

        Parameters can be provided by arguments. If not, we will prompt the user
        for the information.

        Args:
            args: The arguments that have already been collected from the user.
                e.g. {"project_id", "project-123"}

        Returns:
            A dictionary of parameters.

        Raises:
            ValueError: If at least one argument is invalid.
        """
        actual_parameters = {}
        remaining_parameters_to_prompt = {}
        for parameter_name, prompter in (
                self._REQUIRED_PARAMETERS_TO_PROMPT.items()):
            value = getattr(args, parameter_name, None)
            if value is not None:
                try:
                    prompter.validate(value)
                except ValueError as e:
                    print(e, file=sys.stderr)
                    raise
                actual_parameters[parameter_name] = value
            else:
                remaining_parameters_to_prompt[parameter_name] = prompter

        if remaining_parameters_to_prompt:
            num_steps = len(remaining_parameters_to_prompt)
            self._console.tell(
                '<b>{} steps to setup your new project</b>'.format(num_steps))
            self._console.tell()
            parameter_and_prompt = sorted(
                remaining_parameters_to_prompt.items(),
                key=lambda i: self._PROMPT_ORDER.index(i[0]))

            for step, (parameter_name,
                       prompter) in enumerate(parameter_and_prompt):
                step = '<b>[{}/{}]</b>'.format(step + 1, num_steps)
                actual_parameters[parameter_name] = prompter.prompt(
                    self._console, step, actual_parameters,
                    actual_parameters.get('credentials', None))
        return actual_parameters

    def _post_process_args(self, args: argparse.Namespace):
        """Modify prompts based on collected arguments.

        Subclasses should overwrite this method.

        Args:
            args: The arguments that have already been collected from the user
                e.g. {"project_id", "project-123"}
        """
        pass

    def _run(self, parameters: Dict[str, Any]) -> Any:
        """Run the command.

        Subclasses should overwrite this method.

        Args:
            parameters: Parameters necessary to run the command.
        """
        pass

    def execute(self, args):
        try:
            self._post_process_args(args)
            try:
                parameters = self._get_parameters(args)
            except ValueError:
                return
            return self._run(parameters)
        except Exception as e:
            django_cloud_deploy.crash_handling.handle_crash(
                e, 'django-cloud-deploy ' + self.name)
