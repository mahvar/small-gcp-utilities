# Copyright 2019 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys

sys.path.append('../')

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

import datetime

from utils import *


def get_error_messages(http_error):
    """
    Helper function to extract error messages from an HttpError
    :param http_error:
    :return: list of messages found in an HttpError instance
    """

    content_dict = json.loads(http_error.content)  # convert the binary content into a JSON dictionary

    # http_error.content is a dictionary in this shape:
    # {'error':
    #     {'errors': [{}]
    #     }
    # }

    errors_dict = content_dict['error']
    error_messages = []
    for error in errors_dict['errors']:
        error_messages.append(error['message'])

    return error_messages


def get_enabled_api(projectId, credentials):
    """
    Calls https://serviceusage.googleapis.com/v1/projects/{projectId}/services?filter=state:ENABLED
    :param projectId: project id in question
    :param credentials: credentials to be used when making API calls
    :return: list of API that are enabled for the specified project.
    """

    print ('getting list of enabled api for the project {}...'.format(projectId))

    api_list = []
    try:
        service = discovery.build('serviceusage', 'v1', credentials=credentials)
        request = service.services().list(parent='projects/{}'.format(projectId), filter='state:ENABLED')

        response = request.execute()
        if 'services' in response:
            for service in response['services']:
                api_dict = {}
                if 'name' in service['config']:
                    api_dict['name'] = service['config']['name']
                if 'title' in service['config']:
                    api_dict['title'] = service['config']['title']
                if 'quota' in service['config']:
                    api_dict['quota'] = service['config']['quota']

                api_list.append(api_dict)

    except discovery.HttpError as http_error:
        api_list.append({'error': get_error_messages(http_error)})

    return api_list


def get_buckets(projectId, credentials):
    """
    Calls https://www.googleapis.com/storage/v1/b?project=[PROJECT_NAME]
    :param projectId: project Id in question
    :param credentials: credentials to be used when making API calls
    :return: list of buckets under the specified project which the specified credential has access to.
    """

    print('getting list of buckets for the project {}...'.format(projectId))

    bucket_list = []

    try:
        # Try reading list of buckets in the project.
        # If the caller doesn't have proper rights, this will throw an exception.
        service = discovery.build('storage', 'v1', credentials=credentials)
        request = service.buckets().list(project=projectId)

        response = request.execute()

        if 'items' in response:
            for item in response['items']:
                bucket_dict = {'id': item['id'],
                                'name': item['name'],
                                'class': item['storageClass'],
                                'location': item['location'],
                                'created': item['timeCreated'],
                                'updated': item['updated']}

                if 'labels' in item:
                    # Labels are free form and cause errors persisting the json.
                    # We need to convert them into an array of key-value pairs to keep the schema consistent.
                    bucket_dict['labels'] = key_value_pairs(item['labels'])

                try:
                    # Try getting IAM policy bindings for the bucket.
                    # if the caller doesn't have proper rights, this will throw an exception.
                    iam_request = service.buckets().getIamPolicy(bucket=item['name'])
                    iam_response = iam_request.execute()
                    bucket_dict['iam_bindings'] = iam_response['bindings']

                except discovery.HttpError as http_error:
                    bucket_dict['iam_bindings'] = {'error': get_error_messages(http_error)}

                bucket_list.append(bucket_dict)

    except discovery.HttpError as http_error:
        bucket_list.append({'error': get_error_messages(http_error)})

    return bucket_list


def usage():
    print(
        '\nusage: python resource_inventory.py [project filter] [existing BigQuery dataset Id] [new or existing BigQuery table Id]\n')


def main():
    """
    This is how you execute this script:

    python resource_inventory.py [project filter] [BigQuery dataset Id] [BigQuery table Id]

    [project filter]: Wildcard string to specify which projects to inventory. For example,
    to inventory projects with names starting with PROD, you'd pass _name:PROD*_ as project filter.

    [BigQuery dataset Id]: The Id for an existing BiqQuery dataset. The authenticated user must
    have rights to create or update the specified table.

    [BigQuery table Id]: The Id for the table in the specified dataset where the inventory is persisted to.
    If the table doesn't exist, it will be created. Otherwise, new inventory is appended to previous records.
    If appending to an existing table, it has to have the same schema.

    It does the following:

     1) If it cannot find a default application credential, it prompts you to log in.
     2) Retrieves some metadata about all the projects which the authenticated user has access to.
     3) For each project, retrieves:
        - List of enabled API
        - Metadata about all the cloud storage buckets which the authenticated user has access to
     4) Compiles all the metadata about projects and buckets into a single JSON object and persists it in a BigQuery table.
    """

    if len(sys.argv) != 4:
        # Remember sys.argv[0] is always the name of the script. In this case: "resource-inventory.py"
        # We are interested in 3 more arguments besides the script name -> total 4.
        usage()
        return

    project_filter = sys.argv[1]
    dataset_Id = sys.argv[2]
    table_id = sys.argv[3]

    # 0. get the user to login to obtain a google credential
    credentials = GoogleCredentials.get_application_default()

    # 0. start the inventory dictionary with a timestamp
    inventory = {'inventory_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

    # 1. get all the projects the user has access to where they match the specified filter
    service = discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
    request = service.projects().list(filter=project_filter)

    projects = []

    while request is not None:
        response = request.execute()

        if 'projects' in response:
            for project in response['projects']:
                print('getting metadata about project {}...'.format(project['projectId']))

                project_dict = project

                if 'labels' in project_dict:
                    # Labels are free form and cause errors persisting the json.
                    # We need to convert them into an array of key-value pairs to keep the schema consistent.
                    project_dict['labels'] = key_value_pairs(project_dict['labels'])

                try:
                    # 2. get iam bindings at the project level.
                    # if the caller doesn't have proper rights, this will throw an exception.

                    iam_request = service.projects().getIamPolicy(resource=project['projectId'])
                    iam_response = iam_request.execute()
                    project_dict['iam_bindings'] = iam_response['bindings']

                except discovery.HttpError as http_error:
                    project_dict['iam_bindings'] = {'error': get_error_messages(http_error)}

                # 3. get list of enabled API for the project
                project_dict['enabled_api'] = get_enabled_api(project['projectId'], credentials)

                # 4. get list of buckets for the project
                project_dict['buckets'] = get_buckets(project['projectId'], credentials)

                projects.append(project_dict)
        else:
            print ('found no projects matching "{}"!'.format(project_filter))

        request = service.projects().list_next(previous_request=request, previous_response=response)

    if len(projects) > 0:
        print('persisting metadata to BigQuery dataset:{} table:{}...'.format(dataset_Id, table_id))
        inventory['projects'] = projects
        persist_JSON(inventory, dataset_Id, table_id)


if __name__ == '__main__':
    main()
