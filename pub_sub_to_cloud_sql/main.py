"""Source code for a Cloud Function to trigger upon Pub/Sub messages."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import base64
import logging
import pymysql
from pymysql.err import OperationalError


# CHANGE ME: specify SQL connection details
CONNECTION_NAME = 'SQL INSTANCE CONNECTION NAME GOES HERE'
DB_USER = 'SQL USER GOES HERE'
DB_PASSWORD = 'SQL PASSWORD GOES HERE'
DB_NAME = 'DB NAME GOES HERE'
TABLE_NAME = 'TABLE NAME GOES HERE'


# CHANGE ME: Specify the attribute key in the Pub/Sub message
# that can be used as unique identifier handle to de-dupe the messages.
# Note: this is treated as an optional attribute.
HANDLE_ATTRIBUTE_KEY = 'ATTRIBUTE KEY GOES HERE'

# Create SQL connection globally to enable reuse
# PyMySQL does not include support for connection pooling
mysql_conn = None


def on_message(pub_sub_message, context):
    """
    Background Cloud Function to be triggered by Pub/Sub. 
    This is the expected signature by Cloud Function.

    :param pub_sub_message (dict): The dictionary with data specific to this type of event.
    :param context (google.cloud.functions.Context): The Cloud Functions event metadata.
    :return: none
    """

    data = ''
    attributes = {}
    if 'data' in pub_sub_message:
        data = base64.b64decode(pub_sub_message['data']).decode('utf-8')
    else:
        logging.info('Didn\'t find data in the message!')

    if 'attributes' in pub_sub_message:
      attributes = pub_sub_message['attributes']
    else:
      logging.info('Didn\'t find attributes in the message!')

    persist_message(data, attributes)


def persist_message(data, attributes):
    """
    After the Pub/Sub message is separated into data vs. attributes, this
    function persists it as-is in a Cloud SQL table with the following schema:

    time TIMESTAMP,
    data varchar(1000),
    attributes varchar(1000),
    handle varchar(1000)

    If an attribute with the key as specified by HANDLE_ATTRIBUTE_KEY is found 
    among attributes of the Pub/Sub message, its value is used to de-dupe the
    persisted messages.

    :param data (string): The 'data' part of the pub/sub message after it's
    decoded into utf-8 string.
    :param attributes: The 'attributes' dictionary which make up the key/value
    pairs in the pub/sub message.
    :return: none
    """

    if HANDLE_ATTRIBUTE_KEY in attributes:
      # If an older message with the same handle exists,
      # drop it before persisting the new message.
      sql_command = 'DELETE FROM {} WHERE handle="{}";'.format(
          TABLE_NAME, attributes[HANDLE_ATTRIBUTE_KEY])
      execute_command(sql_command)

      sql_command = 'INSERT INTO {} (time, data, attributes, handle) ' \
                    'VALUES ( NOW(), "{}", "{}", "{}")'.format(
          TABLE_NAME,
          data,
          str(attributes),
          attributes[HANDLE_ATTRIBUTE_KEY])
      execute_command(sql_command)

    else:
      sql_command = 'INSERT INTO {} (time, data, attributes) ' \
                    'VALUES ( NOW(), "{}", "{}")'.format(
          TABLE_NAME,
          data,
          str(attributes))

      logging.warning('Missing handle attribute: "{}" in the message! '
                      'Handle attribute is not mandatory, '
                      'but when available is used to de-dupe messages.'.format(
                          HANDLE_ATTRIBUTE_KEY))
      execute_command(sql_command)


def __get_cursor():
    """
    Helper function to get a cursor.
    
    Note: PyMySQL does NOT automatically reconnect,
    so we must reconnect explicitly using ping().
    """

    try:
        return mysql_conn.cursor()
    except OperationalError:
        mysql_conn.ping(reconnect=True)
        return mysql_conn.cursor()


mysql_config = {
    'user': DB_USER,
    'password': DB_PASSWORD,
    'db': DB_NAME,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True
}


def execute_command(sql_command):
    """
    Executes the SQL query it receives as a param using the global my sql
    connection.

    :param sql_command: self-explanatory
    :return: none
    """
    global mysql_conn

    # Initialize connections lazily, in case SQL access isn't needed for this
    # GCF instance. Doing so minimizes the number of active SQL connections,
    # which helps keep your GCF instances under SQL connection limits.
    if not mysql_conn:
      try:
        mysql_conn = pymysql.connect(**mysql_config)
      except OperationalError:
        # If production settings fail, use local development ones
        # cannot import from future:  mysql_config['unix_socket'] = f'/cloudsql/{CONNECTION_NAME}'
        mysql_config['unix_socket'] = '/cloudsql/{}'.format(CONNECTION_NAME)
        mysql_conn = pymysql.connect(**mysql_config)

    # Remember to close SQL resources declared while running this function.
    # Keep any declared in global scope (e.g. mysql_conn) for later reuse.
    with __get_cursor() as cursor:
      logging.info(sql_command)
      cursor.execute(sql_command)
      mysql_conn.commit()
