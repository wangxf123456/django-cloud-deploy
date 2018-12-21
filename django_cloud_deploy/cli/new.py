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
"""Defines a command to create and deploy a new Django project on GKE or GAE."""

import argparse
from typing import Any, Dict

from django_cloud_deploy import workflow
from django_cloud_deploy.cli import command_base
from django_cloud_deploy.cli import prompt


class New(command_base.Command):
    """Create and deploy a new Django project on GKE or GAE."""

    _NAME = 'new'

    _PROMPT_ORDER = [
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

    _REQUIRED_PARAMETERS_TO_PROMPT = {
        'credentials': prompt.CredentialsPrompt,
        'project_id': prompt.ProjectIdPrompt,
        'project_name': prompt.GoogleCloudProjectNamePrompt,
        'billing_account_name': prompt.BillingPrompt,
        'database_password': prompt.PostgresPasswordPrompt,
        'django_directory_path': prompt.DjangoFilesystemPath,
        'django_project_name': prompt.DjangoProjectNamePrompt,
        'django_app_name': prompt.DjangoAppNamePrompt,
        'django_superuser_login': prompt.DjangoSuperuserLoginPrompt,
        'django_superuser_password': prompt.DjangoSuperuserPasswordPrompt,
        'django_superuser_email': prompt.DjangoSuperuserEmailPrompt
    }

    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser):
        """Register flags for this command.

        Args:
            parser: The parser to get registered.
        """

        parser.add_argument(
            '--project-name',
            dest='project_name',
            help=('The name of the Google Cloud Platform project. '
                  'Can be changed.'))

        parser.add_argument(
            '--project-id',
            dest='project_id',
            help='The unique id to use when creating the Google Cloud Platform '
            'project. Can not be changed.')

        parser.add_argument(
            '--project-path',
            dest='django_directory_path',
            help=('The location where the generated Django project code '
                  'should be stored.'))

        parser.add_argument(
            '--database-password',
            dest='database_password',
            help='The password for the default database user.')

        parser.add_argument(
            '--django-project-name',
            dest='django_project_name',
            help='The name of the Django project e.g. "mysite".')

        parser.add_argument(
            '--django-app-name',
            dest='django_app_name',
            help='The name of the Django app e.g. "poll".')

        parser.add_argument(
            '--django-superuser-login',
            dest='django_superuser_login',
            help='The login name of the Django superuser e.g. "admin".')

        parser.add_argument(
            '--django-superuser-password',
            dest='django_superuser_password',
            help='The password of the Django superuser.')

        parser.add_argument(
            '--django-superuser-email',
            dest='django_superuser_email',
            help='The e-mail address of the Django superuser.')

        parser.add_argument(
            '--use-existing-project',
            dest='use_existing_project',
            action='store_true',
            help='Flag to indicate using a new or existing project.')

        parser.add_argument(
            '--backend',
            dest='backend',
            type=str,
            default='gke',
            choices=['gae', 'gke'],
            help='The desired backend to deploy the Django App on.')

        parser.add_argument(
            '--credentials',
            dest='credentials',
            help=('The file path of the credentials file to use for '
                  'deployment. Test only, do not use.'))

        parser.add_argument(
            '--bucket-name',
            dest='bucket_name',
            help=('Name of the GCS bucket to serve static content. '
                  'Test only, do not use.'))

        parser.add_argument(
            '--service-accounts',
            dest='service_accounts',
            nargs='+',
            help=('Service account objects to create for deployment. '
                  'Test only, do not use.'))

        parser.add_argument(
            '--services',
            dest='services',
            nargs='+',
            help=('Services necessary for the deployment. '
                  'Test only, do not use.'))

    def _post_process_args(self,
                           args: argparse.Namespace):
        """Modify prompts based on arguments.

        Args:
            args: Arguments for this command.
        """
        if args.use_existing_project:
            self._REQUIRED_PARAMETERS_TO_PROMPT['project_name'] = (
                prompt.GoogleCloudProjectNamePrompt)
            self._REQUIRED_PARAMETERS_TO_PROMPT['project_id'] = (
                prompt.ExistingProjectIdPrompt)

    @staticmethod
    def _run(parameters: Dict[str, Any]) -> str:
        """Run the new command.

        Args:
            parameters: Required parameters to run the command.

        Returns:
            The url of the deployed Django website.
        """
        workflow_manager = workflow.WorkflowManager(
            parameters.get('credentials'), parameters.get('backend'))
        url = workflow_manager.create_and_deploy_new_project(
            project_name=parameters.get('project_name'),
            project_id=parameters.get('project_id'),
            project_creation_mode=parameters.get('project_creation_mode'),
            billing_account_name=parameters.get('billing_account_name'),
            django_project_name=parameters.get('django_project_name'),
            django_app_name=parameters.get('django_app_name'),
            django_superuser_name=parameters.get('django_superuser_login'),
            django_superuser_email=parameters.get('django_superuser_email'),
            django_superuser_password=parameters.get(
                'django_superuser_password'),
            django_directory_path=parameters.get('django_directory_path'),
            database_password=parameters.get('database_password'),
            required_services=parameters.get('services'),
            required_service_accounts=parameters.get('service_accounts'),
            cloud_storage_bucket_name=parameters.get('bucket_name'),
            backend=parameters.get('backend'))
        return url
