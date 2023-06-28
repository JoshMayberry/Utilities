# Needs to run with a user who has permission to get the certificate for NetSuite and I can't figure out how to add IIS_IUSRS to it; So use jmayberry and the NetSuite routien can run.

import os
import sys
import logging
import contextlib

import pyodbc

import PyUtilities.common
import PyUtilities.logger
from PyUtilities.datasource.common import config

@contextlib.contextmanager
def getConnection(*, _self=None, connection=None, configKwargs=None, driver="NetSuite Drivers 64bit",
	host=None, dbname=None, user=None, password=None, account=None, **kwargs):
	"""
	Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16#download-for-windows
	"""

	if (connection is not None):
		yield connection
		return

	logging.info("Opening NetSuite ODBC connection...")

	user = user or config("user", "netsuite", **(configKwargs or {}))
	password = password or config("password", "netsuite", **(configKwargs or {}))
	account = account or config("account", "netsuite", **(configKwargs or {}))

	_connection = pyodbc.connect(f"DSN=NetSuite", user=user, password=password)
	
	with _connection:
		yield _connection

	logging.info("Closing NetSuite ODBC connection...")
	_connection.close()

def getWarehouseManagerToken():
	""" To use role 57, you need to generate a new token for every transaction using this power shell script. """

	powerShellScript = f"""
		$nonce = ''
		$set = "abcdefghijklmnopqrstuvwxyz0123456789".ToCharArray()
		for ($x = 0; $x -lt 20; $x++) {{
		$nonce += $set | Get-Random
		}}
		$account = '{account}' #Your NS Account ID
		#Copy these values from your NS Account
		$consumer_Key = '{consumer_id}'
		$consumer_secret = '{consumer_secret}'
		$token = '{token_id}'
		$token_secret = '{token_secret}'
		$timestamp = [int][double]::Parse((Get-Date (get-date).touniversaltime() -UFormat %s))
		$timestamp = [string]$timestamp
		$msg = $account + '&' + $consumer_Key + '&' + $token + '&' + $nonce + '&' + $timestamp
		$secret = $consumer_secret + '&' + $token_secret
		$hmacsha = New-Object System.Security.Cryptography.HMACSHA256
		$hmacsha.key = [Text.Encoding]::ASCII.GetBytes($secret)
		$signature = $hmacsha.ComputeHash([Text.Encoding]::ASCII.GetBytes($msg))
		$signature = [Convert]::ToBase64String($signature)
		$tokenpass = $account + '&' + $consumer_Key + '&' + $token + '&' + $nonce + '&' + $timestamp + '&' + $signature + '&HMAC-SHA256'
		echo $tokenpass
	"""

def select(*args, **kwargs):
	return tuple(yield_select(*args, **kwargs))

def yield_select(query_sql, query_args=None, **kwargs):
	""" Yields data from the given query.
	See: https://www.netsuite.com/help/helpcenter/en_US/srbrowser/Browser2018_1/odbc/record/transaction.html

	Example Input: yield_select("SELECT email, COUNT(*) as count FROM transaction GROUP BY email")
	"""

	with getConnection(**kwargs) as connection:
		with connection.cursor() as cursor:
			cursor.execute(query_sql, query_args or ())

			columns = [column[0] for column in cursor.description]
			row = cursor.fetchone()
			while row:
				yield dict(zip(columns, row))
				row = cursor.fetchone()

if (__name__ == "__main__"):
	PyUtilities.logger.logger_info()

	with getConnection() as connection:
		for item in select("SELECT TOP 2 * FROM Account", connection=connection):
			print(item)