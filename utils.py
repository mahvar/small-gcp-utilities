from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import subprocess
import io
import json


def run_command(cmd, safe_message_indicator='', interrupt_on_error=True, chatty=True):
    # type: (object, object, object, object) -> object
    """
    Runs the provided shell command and returns the resultant message.

    :param cmd: a shell command to execute

    :param interrupt_on_error: instructions on how to handle a failed command. True
    indicates an important step in the script, which if failed, causes the script to break.

    :param safe_message_indicator: a phrase which when seen in the command output, indicates the error is safe to ignore.

    :param chatty: when set to True, the command and the resultant message are printed on the console.

    :return: the message that was communicated by the shell command.

    Note: If the command doesn't finish with 0 as the return code,
    the message doesn't contain an expected phrase and interrupt_on_error is set to True, an exception is raised.
    """
    if chatty:
        print ('>>>command: ' + cmd)

    osstdout = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, close_fds=True)

    message = osstdout.communicate()[0].strip()
    if chatty:
        print('>>>message: ' + message)

    if osstdout.returncode is not 0:
        if interrupt_on_error:
            if not safe_message_indicator or message.find(safe_message_indicator) is -1:
                raise Exception(message)

    return message


# Make it work for Python 2 and 3 and with Unicode
try:
    to_unicode = unicode
except NameError:
    to_unicode = str


def save_pretty_JSON(jsonDict, outputFileName):
    """
    Writes the provided dictionary into the output file in JSON format.
    :param jsonDict: the dictionary to be saved
    :param outputFile: the file to be saved to
    :return: None
    """
    with io.open(outputFileName, 'w', encoding='utf8') as outputFile:
        str_ = json.dumps(jsonDict,
                    indent=4,
                    sort_keys=True,
                    separators=(',', ': '),
                    ensure_ascii=False)
        outputFile.write(to_unicode(str_))


def key_value_pairs(input_dict):
    """
    Coverts a dictionary into a flat list of key-value pairs.
    :param input_dict: e.g. {'name': 'A', 'type': 'B'}
    :return: e.g. [{'key': 'name', 'value': 'A'}, {'key': 'type', 'value': 'B'}]
    """
    output_list = []
    for key, value in input_dict.items():
        output_list.append({'key': key, 'value': value})

    return output_list


def save_new_line_delimited_JSON(jsonArray, outputFileName):
    """
    Converts the input array of dictionaries into newline delimited JSON and writes it to the output file.
    :param jsonDict: the array of dictionaries to be saved
    :param outputFile: the file to be saved to
    :return: None
    """
    in_json = json.dumps(jsonArray).replace("\'", "\"")  # convert single quotes to double quotes

    with io.open(outputFileName, 'w', encoding='utf8') as outputFile:
        result = [json.dumps(record) for record in json.loads(in_json)]

        str_ = '\n'.join(result)
        outputFile.write(to_unicode(str_))


def merge_JSON(jsonDict, inOutFile):
    """
    Merges the provided  dictionary into the content of the named JSON file.
    :param jsonDict: the dictionary to be saved
    :param inOutFile: the file where the  dictionary is merged to

    :return: none
    """
    __file_dict = json.load(open(inOutFile))
    __merged_dict = dict(__file_dict, **jsonDict)

    with io.open(inOutFile, 'w', encoding='utf8') as outfile:
        str_ = json.dumps(__merged_dict,
                          indent=4, sort_keys=True,
                          separators=(',', ': '), ensure_ascii=False)

        outfile.write(str_.decode("utf-8"))


def persist_JSON(json_dict, dataset_id, table_id):
    """
    Persists provided dictionary as a SINGLE row with nested and repeated columns into BigQuery.
    If unfamiliar with nested and repeated columns, refer to https://cloud.google.com/bigquery/docs/nested-repeated.

    :param json_dict: a SINGLE object definition to be persisted.
    :param dataset_id: The Id of an EXISTING BigQuery dataset.
    :param table_id: The Id of the BigQuery table where the JSON is to be persisted.
    If table doesn't exist, it will be created.

    :return: None
    """

    from google.cloud import bigquery
    import os

    _tempFile = "tmp.json"

    save_new_line_delimited_JSON([json_dict], _tempFile)

    client = bigquery.Client()

    dataset_ref = client.dataset(dataset_id)
    dataset_location = client.get_dataset(dataset_ref).location

    table_ref = dataset_ref.table(table_id)
    job_config = bigquery.LoadJobConfig()
    job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    job_config.autodetect = True

    with open('tmp.json', 'rb') as source_file:
        job = client.load_table_from_file(
            source_file,
            table_ref,
            location=dataset_location,  # Must match the destination dataset location.
            job_config=job_config)      # API request

    job.result()  # Waits for table load to complete.

    print('Loaded {} rows into {}:{}.'.format(
        job.output_rows, dataset_id, table_id))

    os.remove(_tempFile) # Delete temp json file


