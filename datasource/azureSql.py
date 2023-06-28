import os
import sys
import logging
import contextlib

import pyodbc

import PyUtilities.common
from PyUtilities.datasource.common import config

@contextlib.contextmanager
def getConnection(*, _self=None, driver="ODBC Driver 18 for SQL Server", connection=None, configKwargs=None, 
	host=None, dbname=None, user=None, password=None, port=None, **kwargs):
	"""
	Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16#download-for-windows
	"""

	if (connection is not None):
		yield connection
		return

	logging.info("Opening AzureSQL connection...")

	host = host or config("host", **(configKwargs or {}))
	dbname = dbname or config("dbname", **(configKwargs or {}))
	user = user or config("user", **(configKwargs or {}))
	password = password or config("password", **(configKwargs or {}))
	port = port or config("port", **(configKwargs or {}))

	_connection = pyodbc.connect(f"DRIVER={{{driver}}};SERVER={host},{port}", user=user, password=password, database=dbname)
	if (_self is None):
		with _connection:
			yield _connection
	else:
		with _connection:
			_self._connection = _connection
			yield _connection
			_self._connection = None
	logging.info("Closing postgres connection...")
	_connection.close()

if (__name__ == "__main__"):
	PyUtilities.logger.logger_info()

	with getConnection(configKwargs={"section": "netsuite_faztrack"}) as connection:
		with connection.cursor() as cursor:
			cursor.execute("SELECT TOP 200 x.* FROM vineyardsDB_SandBox.dbo.NS_Actual_Income_Data x")
			row = cursor.fetchone()
			while row:
				print (str(row[0]) + " " + str(row[1]))
				row = cursor.fetchone()