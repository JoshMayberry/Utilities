import os
import sys
import json
import logging
import datetime
import contextlib

import numpy
import pandas
import dateutil

import psycopg2
import psycopg2.extras

import PyUtilities.common
import PyUtilities.logger
import PyUtilities.testing
import PyUtilities.datasource.common
import PyUtilities.datasource.general
from PyUtilities.datasource.common import config

def get_last_modifier(self=None, *, routineName=None, method=None, extra=None):
	if (self is None):
		if ((routineName is None) or (method is None)):
			raise KeyError("Must pass in *routineName* and *method* if *self* is None")

	return f"Python: {'dev.' if PyUtilities.datasource.common.is_dev else ''}TableUpdater.{routineName or self.routineName}.{method or self.method}" + (f".{extra}" if extra else "")

def _renameKeys(iterable):
	""" A recursive function to convert keys to lowercase.
	Otherwise, json keys won't match postgresql column names.

	iterable (list or dict) - What to iterate over

	Example Input: _renameKeys([{"Lorem": 1, "IPSUM": 2, "dolor": 3}])
	"""

	if isinstance(iterable, dict):
		new_object = {}
		for (key, value) in iterable.items():
			new_object[key.lower()] = value if not isinstance(iterable, (dict, list, tuple)) else _renameKeys(value)
		return new_object

	if isinstance(iterable, (list, tuple)):
		return [_renameKeys(item) for item in iterable]

	return iterable

def insert(data, table, *, schema=None, method="upsert", insert_method="single", drop_where=None, ignore=None, returning=None,
	upsert_constraint=None, reset_incrementer=None, lowerNames=False, typeCatalogue=None, configKwargs=None, update_changed=False, replace_nan=True,
	preInsert=None, postInsert=None, update_set=None, update_where=None, chunk_size=900, backup=None, log_import=None, log_table=True, **kwargs):
	""" Adds data to a postgres database.
	See: https://www.psycopg.org/docs/usage.html#query-parameters
	Use: http://www.postgresqltutorial.com/postgresql-python/connect/

	data (tuple of dict) - What to send to the database
	table (str) - Which table to send the data to
	method (str) - How to handle sending the data
		- insert: Inserts a row if it does not yet exist
		- insert_ignore: Inserts a row if it does not yet exist; skips conflicts
		- update: Update a row if it exists
		- update_ignore: Updates a row if it exists; skips conflicts
		- upsert: Update existing data in the db, otherwise insert a new row
		- drop: Drop all rows in the table and insert new rows
		- truncate: Cleanly drop all rows in the table and insert new rows  (See: https://stackoverflow.com/questions/11419536/postgresql-truncation-speed/11423886#11423886)
		- If Function: Will use a string returned by it as what to do for an individual row
	insert_method (str) - How to handle inserting things into the database
		- json: Pass in a JSON string with all the data (Does not allow non-serializable inputs such as datetime objects)
		- separate: Do an individual insert for each row (Much slower)
		- single: Do a single insert statement for every *chunk_size* rows
	backup (dict or str) - How to backup what is inserted
		- kind (required): Used as the string
			- dropbox: Send to dropbox
			- onedrive: Send to onedrive
			- blob: Send to blob storage
		- other keys: kwargs to send
		- If str: Assumed to be *backup.kind*
	lowerNames (bool) - If object keys should be lower-cased
	typeCatalogue (dict) - What type specific columns need to be; where the key is the column name and the value is one of the following strings:
		- json: The data should be a JSON string (will fail if the column's value contains non-serializable values)
	drop_where (str) - What to use for selecting what is dropped
	update_changed (bool or str) - If only existing items that have been changed should be updated
		- If str or list of str: Which column(s) to look at for if a change has happened or not

	Example Input: insert([{"lorem": "ipsum"}], "property")
	Example Input: insert([{"Lorem": "ipsum"}], "property", lowerNames=True)
	Example Input: insert([{"lorem": "ipsum"}], "property", backup="dropbox")
	Example Input: insert([{"lorem": "ipsum"}], "property", backup={"kind": "dropbox", "folder": "rps"})
	Example Input: insert([{"lorem": "ipsum"}], "property", backup={"kind": "dropbox", "filename_subname": "treehouse"})
	Example Input: insert([{"lorem": datetime.datetime.now()}], "property", insert_method="separate")
	Example Input: insert(frame, "property")
	Example Input: insert([{"lorem": "ipsum"}], "property", method="drop")
	Example Input: insert([{"lorem": {"ipsum": 1}}], "property", typeCatalogue={"lorem": "json"})
	Example Input: insert([[{"lorem": "ipsum"}], [{"dolor": "sit"}]], "property")
	Example Input: insert([frame_1, frame_2], "property")
	Example Input: insert(frame, "property", method=lambda row, context: "insert" if row["should_insert"] else "skip", insert_method="single")
	Example Input: insert(frame, "property", method="update")
	Example Input: insert(frame, "property", method="update", update_set=["lorem", "ipsum"])
	Example Input: insert(frame, "property", method="update", update_where="dolor")
	Example Input: insert([{"lorem": "ipsum"}], "property", returning="property_id")
	Example Input: insert([{"lorem": "ipsum"}], "property", returning="property_id as prop_code")
	"""

	def yield_sqlUpdate(_data, _method):
		no_ignore = (_method != "update_ignore")
		no_return = not returning
		
		match insert_method:
			case "json":
				raise NotImplementedError("Update json")

			case "separate":
				for row in _data:
					_update_set = update_set
					if (not _update_set):
						_update_set = tuple(key for key in row.keys() if (key not in update_where))
						_update_set = PyUtilities.common.ensure_container(_update_set)

					valueList = []
					valueList.extend(row.get(key) for key in _update_set)
					valueList.extend(row.get(key) for key in update_where)

					yield [
						f"""UPDATE {schema}.{table} SET {', '.join(f'"{key}" = %s' for key in _update_set)} WHERE ({', '.join(f'{key} = %s' for key in update_where)})""" +
							("" if no_ignore else " ON CONFLICT DO NOTHING") +
							("" if no_return else f" RETURNING {returning}"),
						valueList
					]
					
			case "single":
				for chunk in (_data[i:i+chunk_size] for i in range(0, len(_data), chunk_size)):
					_update_set = update_set
					if (not _update_set):
						_update_set = tuple(key for key in chunk[0].keys() if (key not in update_where))
						_update_set = PyUtilities.common.ensure_container(_update_set) # TODO: Is this line needed?

					keyList = set(_update_set + update_where)

					valueCatalogue = {}
					valueListCatalogue = {}

					for key in keyList:
						valueList = []
						valueListCatalogue[key] = valueList

						for (j, row) in enumerate(chunk):
							valueList.append(f"%({key}_{j})s")
							valueCatalogue[f"{key}_{j}"] = row.get(key)

					yield [
						f"""UPDATE {schema}.{table} SET {', '.join(f'"{key}" = a.{key}' for key in _update_set)} FROM (SELECT """ +
							", ".join(f"""unnest(array[{', '.join(valueList)}]) as "{key}\"""" for (key, valueList) in valueListCatalogue.items()) +
							f") as a WHERE ({' AND '.join(f'{table}.{key} = a.{key}' for key in update_where)})" + 
							("" if no_ignore else " ON CONFLICT DO NOTHING") +
							("" if no_return else f" RETURNING {returning}"),
						valueCatalogue
					]

			case _:
				raise KeyError(f"Unknown *insert_method* '{insert_method}'")

	def yield_sqlInsert(_data, _method):
		if (_method == "skip"):
			return

		if (update_changed and _method.startswith("up")):
			# Make sure key columns are present
			frame_new = pandas.DataFrame(_data)
			_update_changed = [key for key in update_changed if (key in frame_new.columns)]

			if (_update_changed):
				if (any((key not in frame_new.columns) for key in columns_constraint)):
					logging.error({"columns_constraint": columns_constraint, "columns": frame_new.columns})
					raise ValueError("Missing one or more keys in *_data*")

				# Get current values for data set
				valueCatalogue = {}
				valueListCatalogue = {}
				for [i, row] in enumerate(_data):
					valueList = []
					valueListCatalogue[i] = valueList

					for key in columns_constraint:
						valueList.append(f'"{key}" = %({key}_{i})s')
						valueCatalogue[f"{key}_{i}"] = row.get(key, None)

				sql_raw = f"""
					SELECT
						{", ".join(f'"{key}"' for key in (*columns_constraint, *_update_changed))}
					FROM
						{schema}.{table}
					WHERE
						{ " OR ".join(f"({' AND '.join(rowValues)})" for rowValues in valueListCatalogue.values()) }
				"""

				# Determine Changed Rows
				# See: https://stackoverflow.com/questions/53380310/how-to-add-suffix-to-column-names-except-some-columns/66553586#66553586
				# See: https://stackoverflow.com/questions/41815079/pandas-merge-join-two-data-frames-on-multiple-columns/41815118#41815118
				frame_existing = pandas.DataFrame(raw(sql_raw, valueCatalogue, as_dict=True, **kwargs)) \
					.rename(columns={
						key: f"{key}__old" for key in frame_new.columns if (key not in columns_constraint)
					})

				if (frame_existing.empty):
					frame_changed = frame_new;
					logging.info(f"{len(frame_changed.index)} of the given {len(_data)} new rows are to be added")
				else:
					frame_changed = pandas.merge(frame_new, frame_existing, on=columns_constraint, how="left", indicator=True) \
						.query("(_merge == 'left_only') | " + " | ".join(
							f"(({key}.notna() | {key}__old.notna()) & ({key} != {key}__old))" for key in _update_changed
						))[frame_new.columns]
					
					logging.info(f"{len(frame_changed.index)} of the given {len(_data)} rows have changed and will be actually updated")

				_data = frame_changed.to_dict("records")
				if (not len(_data)):
					return

		if ((_method == "update") or (_method == "update_ignore")):
			for item in yield_sqlUpdate(_data, _method):
				yield item
			return

		if (reset_incrementer):
			yield [f"SELECT setval(pg_get_serial_sequence('{schema}.{table}', '{reset_incrementer}'), GREATEST(COALESCE(MAX({reset_incrementer}), 1), 1), MAX({reset_incrementer}) IS NOT null) FROM {schema}.{table}", ()]

		no_update = (_method != "upsert")
		no_ignore = (_method != "insert_ignore")
		no_return = not returning
		match insert_method:
			case "json":
				yield [
					f"INSERT INTO {schema}.{table} SELECT p.* FROM jsonb_populate_recordset(NULL::{schema}.{table}, %s) as p" +
						("" if no_update else f""" ON CONFLICT ON CONSTRAINT {upsert_constraint} DO UPDATE SET {', '.join(f'"{key}" = EXCLUDED.{key}' for key in _data[0].keys())}""") +
						("" if no_ignore else f" ON CONFLICT DO NOTHING") +
						("" if no_return else f" RETURNING {returning}"),
					(json.dumps(_data),)
				]

			case "separate":
				for row in _data:
					keyList = tuple(row.keys())
					yield [
						f"""INSERT INTO {schema}.{table} ({', '.join(f'"{key}"' for key in keyList)}) VALUES ({', '.join(f'%({key}_0)s' for key in keyList)})""" +
							("" if no_update else f""" ON CONFLICT ON CONSTRAINT {upsert_constraint} DO UPDATE SET {', '.join(f'"{key}" = EXCLUDED.{key}' for key in keyList)}""") +
							("" if no_ignore else f" ON CONFLICT DO NOTHING") +
							("" if no_return else f" RETURNING {returning}"),
						{f"{key}_0": value for (key, value) in row.items()}
					]

			case "single":
				keyList = tuple(_data[0].keys())

				for chunk in (_data[j:j+chunk_size] for j in range(0, len(_data), chunk_size)):
					valueList = []
					valueCatalogue = {}
					for (j, row) in enumerate(chunk):
						valueList.append(f"({', '.join(f'%({key}_{j})s' for key in keyList)})")
						valueCatalogue.update({f"{key}_{j}": value for (key, value) in row.items()})

					yield [
						f"""INSERT INTO {schema}.{table} ({', '.join(f'"{key}"' for key in keyList)}) VALUES {', '.join(valueList)}""" +
							("" if no_update else f""" ON CONFLICT ON CONSTRAINT {upsert_constraint} DO UPDATE SET {', '.join(f'"{key}" = EXCLUDED.{key}' for key in keyList)}""") +
							("" if no_ignore else f" ON CONFLICT DO NOTHING") +
							("" if no_return else f" RETURNING {returning}"),
						valueCatalogue
					]

			case _:
				raise KeyError(f"Unknown *insert_method* '{insert_method}'")

	def doInsert(_data, i, connection):
		if (not len(_data)):
			logging.info(f"No data to insert into '{schema}.{table}' for item number '{i}'")
			return ((), ())

		if (isinstance(_data, pandas.DataFrame)):
			if (_data.empty):
				logging.info(f"No data to insert into '{schema}.{table}' for item number '{i}'")
				return ((), ())

			# See: https://pandas.pydata.org/pandas-docs/version/0.17.0/generated/pandas.DataFrame.to_dict.html#pandas.DataFrame.to_dict
			_data = _data.replace({numpy.nan: None}).to_dict("records")

		elif (isinstance(_data, dict)):
			raise ValueError("Data was not given in the correct format for this function; Make sure it is a container")
			# _data = (_data,)

		if (lowerNames):
			_data = _renameKeys(_data)

		if (ignore):
			keyList = tuple(_data[0].keys())

			for key in ignore:
				if (key not in keyList):
					continue

				for catalogue in _data:
					del catalogue[key]

		if (replace_nan):
			for row in _data:
				for (key, value) in row.items():
					if ((not isinstance(value, (list, tuple, set))) and pandas.isnull(value)):
						row[key] = None # Ensure no NaN or NaT values

		if (typeCatalogue):
			for (key, value) in typeCatalogue.items():
				for row in _data:
					if (key not in row):
						continue

					item = row[key]
					match value:
						case "json":
							if (isinstance(item, str)):
								continue
							
							row[key] = json.dumps(item)

						case "int":
							row[key] = int(item)

						case "datetime" | "date":
							if (isinstance(item, datetime.datetime) or (item is None)):
								continue

							# See: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
							# See: https://stackoverflow.com/questions/23581128/how-to-format-date-string-via-multiple-formats-in-python/23581184#23581184
							try:
								row[key] = dateutil.parser.parse(item)
							except dateutil.parser._parser.ParserError:
								found = False
								for date_format in ("%Y-%m-%d_%H-%M-%S",):
									try:
										row[key] = datetime.datetime.strptime(item, date_format)
										found = True
										break

									except ValueError:
										pass

								if (not found):
									raise ValueError(f"Unknown {value} format: '{item}'")

						case _:
							raise KeyError(f"Unknown *typeCatalogue[{key}]* '{value}'; {[item]}")

		queries = []
		if ((not i) and (method in ("drop", "truncate"))):
			# Only do this for the first item
			match method:
				case "drop":
					queries.append([f"DELETE FROM {schema}.{table}{'' if not drop_where else f' WHERE ({drop_where})'}", ()])

				case "truncate":
					queries.append([f"TRUNCATE TABLE {schema}.{table} RESTART IDENTITY", ()])

				case _:
					raise KeyError(f"Unknown *method* '{method}'")

		if (isinstance(method, str)):
			queries.extend(yield_sqlInsert(_data, method))

			# print("DEBUGGING: NO QUERY SENT\n")
			answer = runSQL(queries, **{"connection":connection, **kwargs})
			return (answer, _data)

		data_drop = []
		data_insert = []
		data_insert_ignore = []
		data_update = []
		data_update_ignore = []
		data_upsert = []
		skip_count = 0

		total = len(_data)
		for (j, row) in enumerate(_data):
			key = method(row, {
				"batch_count": i,
				"row_count": j,
			})
			match key:
				case "drop":
					data_drop.append(row)

				case "insert":
					data_insert.append(row)

				case "insert_ignore":
					data_insert_ignore.append(row)

				case "update":
					data_update.append(row)

				case "update_ignore":
					data_update_ignore.append(row)

				case "upsert":
					data_upsert.append(row)

				case "skip":
					skip_count += 1
					continue

				case None:
					skip_count += 1
					continue

				case _:
					raise KeyError(f"Unknown *method() answer* '{key}'")

		if (data_drop):
			logging.info(f"Will drop {len(data_drop)} of {total} rows")
			raise NotImplementedError("Drop row without knowing the primary key")

		if (data_insert):
			logging.info(f"Will insert {len(data_insert)} of {total} rows")
			queries.extend(yield_sqlInsert(data_insert, "insert"))

		if (data_insert_ignore):
			logging.info(f"Will insert or ignore {len(data_insert_ignore)} of {total} rows")
			queries.extend(yield_sqlInsert(data_insert_ignore, "data_insert_ignore"))

		if (data_update):
			logging.info(f"Will update {len(data_update)} of {total} rows")
			queries.extend(yield_sqlInsert(data_update, "update"))

		if (data_update_ignore):
			logging.info(f"Will update or ignore {len(data_update_ignore)} of {total} rows")
			queries.extend(yield_sqlInsert(data_update_ignore, "data_update_ignore"))

		if (data_upsert):
			logging.info(f"Will upsert {len(data_upsert)} of {total} rows")
			queries.extend(yield_sqlInsert(data_upsert, "upsert"))

		if (skip_count):
			logging.info(f"Will skip {skip_count} of {total} rows")

		# print("DEBUGGING: NO QUERY SENT\n")
		answer = runSQL(queries, **{"connection": connection, **kwargs})
		return (answer, (*data_drop, *data_insert, *data_update, *data_upsert))

	def formatData(_data):
		container = PyUtilities.common.ensure_container(_data, checkIteratorFunction=lambda item: not isinstance(item, pandas.DataFrame))
		if (not container):
			return ()

		if (isinstance(container[0], dict)):
			return (container,)

		return container

	#################################

	schema = schema or "public"
	upsert_constraint = upsert_constraint or f"{table}_pkey"
	update_where = PyUtilities.common.ensure_container(update_where or f"{table}_id")
	ignore = PyUtilities.common.ensure_container(ignore or None)
	returning = ", ".join(PyUtilities.common.ensure_container(returning or None))

	if (update_set):
		update_set = PyUtilities.common.ensure_container(update_set)

	last_i = -1
	recieved = []
	data_used = []
	with getConnection(**kwargs) as connection:
		if (not isinstance(update_changed, bool)):
			update_changed = PyUtilities.common.ensure_container(update_changed)
		elif (update_changed):
			update_changed = getColumns(table, schema=schema, remove=("date_created", "date_modified", "last_modifier", "modify_count", "date_api"), connection=connection)

		if (update_changed):
			columns_constraint = getColumns_constraint(upsert_constraint, table=table, schema=schema, connection=connection)
			update_changed = [key for key in update_changed if key not in columns_constraint]

		if (preInsert):
			for (i, _data) in enumerate(formatData(preInsert()), start=last_i + 1):
				_recieved, _data_used = doInsert(_data, i, connection)
				data_used.extend(_data_used)
				recieved.extend(_recieved)
				last_i = i

		for (i, _data) in enumerate(formatData(data), start=last_i + 1):
			_recieved, _data_used = doInsert(_data, i, connection)
			data_used.extend(_data_used)
			recieved.extend(_recieved)
			last_i = i

		if (postInsert):
			for (i, _data) in enumerate(formatData(postInsert()), start=last_i + 1):
				_recieved, _data_used = doInsert(_data, i, connection)
				data_used.extend(_data_used)
				recieved.extend(_recieved)
				last_i = i

		if (not len(data_used)):
			logging.info(f"No data was inserted into '{schema}.{table}' after {last_i} runs")
			return ((), ())

		if (log_import):
			log_import = PyUtilities.common.ensure_dict(log_import, "path")
			log_import__path = log_import.get("path", None)
			if (not log_import__path):
				raise KeyError(f"Missing *path* in *log_import*; {log_import}")

			insert(
				data=[{
					"path": log_import__path,
					"group": log_import.get("group", "Unknown"),
					"last_modifier": log_import.get("last_modifier", "Unknown"),
					"date_file_modified": log_import.get("date_file_modified", None) or f"{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}",
				}],
				table="log_import",
				method="upsert",
				reset_incrementer="log_import_id",
				upsert_constraint="log_import_un",
				typeCatalogue={
					"date_file_modified": "datetime",
				},
				connection=connection,
				log_table=False,
			)

		if (log_table):
			log_table = PyUtilities.common.ensure_dict(log_table, "path")
			log_table__path = log_table.get("path", None)
			if (not log_table__path):
				raise KeyError(f"Missing *path* in *log_table*; {log_table}")

			insert(
				data=[{
					"schema": schema,
					"table": table,
					"comment": log_table.get("comment", None),
					"last_modifier": log_table.get("last_modifier", None) or 
						(data_used[0]["last_modifier"] if (data_used and ("last_modifier" in data_used[0])) else None) or 
						"Unknown",
				}],
				table="log_table",
				method="upsert",
				reset_incrementer="log_table_id",
				upsert_constraint="log_table_un",
				connection=connection,
				log_table=False,
			)

	if (backup):
		backup = PyUtilities.common.ensure_dict(backup, "kind")
		kind = backup.get("kind", None)
		folder = table if (schema == "public") else f"{schema}__{table}"

		if (not backup.get("filename", None)):
			# See: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
			subname = backup.get("filename_subname", None)

			# backup["filename"] = f"{f'{subname}_' if subname else ''}{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.csv"
			backup["filename"] = f"{f'{subname}_' if subname else ''}{table}.csv"


		match kind:
			case "dropbox":
				logging.info(f"TODO: DIRECT THESE TO SHAREPOINT INSTEAD OF DROPBOX")
				# Dropbox.insert(data_used, folder=folder, input_type="csv", **backup)

			case "onedrive":
				OneDrive.insert(data_used, folder=folder, input_type="csv", **backup)

			case "blob":
				BlobStorage.insert(data_used, folder=folder, input_type="csv", **backup)

			case None:
				raise ValueError("Required key missing: *backup.kind*")

			case _:
				raise KeyError(f"Unknown *backup.kind* '{kind}'")

	return (recieved, data_used)

# def update(frame, table, column, *, pk=None, method="upsert", upsert_constraint=None, reset_incrementer=None, connection=None):
# 	""" Does a batch update statement.
# 	See: https://stackoverflow.com/questions/7019831/bulk-batch-update-upsert-in-postgresql/20224370#20224370

# 	Example Input: update(frame, table="sos", column="code")
# 	Example Input: update(frame, table="sos", column={"sos_code": "code"})
# 	"""

# 	pk = pk or f"{table}_id"

# 	catalogue_column = PyUtilities.common.ensure_dict(column, useAsKey=None)
# 	columnList = tuple(catalogue_column.keys())

# 	sql_set = ", ".join(f"{key} = b.{key}" for key in columnList)
# 	sql_from = ", ".join(f"unnest(array[{', '.join(v)}]) as {key}")

# 	sql_full = f"UPDATE {table} as a SET {sql_set} FROM (SELECT {sql_from}) as b WHERE (a.{pk} = b.{pk})",

# 	raw(query_sql=sql_full, as_dict=False, connection=connection)

def yield_raw(query_sql, query_args=None, **kwargs):
	""" Yields the answer to a raw sql statement to ther database.
	See: https://www.psycopg.org/docs/connection.html

	table (str) - Which table to get data from
	
	Example Input: yield_raw("SELECT * FROM property")
	Example Input: yield_raw("SELECT * FROM property WHERE id = %s", (1,))
	Example Input: yield_raw("SELECT id FROM property", as_dict=False)
	Example Input: yield_raw((("SELECT * FROM property", ()), ("SELECT * FROM property WHERE id = %s", (1,))))
	"""

	for item in (yield_runSQL(((query_sql, query_args),), **kwargs) if isinstance(query_sql, str) else yield_runSQL(query_sql, **kwargs)):
		yield item

def raw(*args, **kwargs):
	return tuple(yield_raw(*args, **kwargs))

@contextlib.contextmanager
def getConnection(*, _self=None, connection=None, configKwargs=None, **kwargs):
	if (connection is not None):
		yield connection
		return

	logging.info("Opening postgres connection...")
	_connection = psycopg2.connect(**config(**(configKwargs or {})))
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

def yield_runSQL(queries, *, as_dict=PyUtilities.common.NULL_private, nested=0, nested_max=3, **kwargs):
	# See: https://www.psycopg.org/docs/connection.html
	
	with getConnection(**kwargs) as connection:
		with (connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) if (as_dict or (as_dict is PyUtilities.common.NULL_private)) else connection.cursor()) as cursor:
			logging.info(f"Sending {len(queries)} queries...")
			for (query_sql, query_args) in queries:
				logging.debug(PyUtilities.logger.debugging and f"query_sql: '{query_sql}'")
				logging.debug(PyUtilities.logger.debugging and f"query_args: '{query_args}'")
				try:
					# TODO logging.info how many rows were added, modified, deleted, etc
					# See: https://www.geeksforgeeks.org/python-psycopg2-getting-id-of-row-just-inserted/
					cursor.execute(query_sql, query_args or ())

					if (query_sql.startswith("SELECT setval(pg_get_serial_sequence(")):
						continue # Do not save the reset_incrementer value
					
					if (as_dict is PyUtilities.common.NULL_private):
						_as_dict = True if (query_sql[:6].lower().startswith("select") or ("RETURNING" in query_sql)) else None
					else:
						_as_dict = as_dict

					if (_as_dict is not None):
						count = 0

						if (_as_dict):
							for row in cursor:
								count += 1
								yield dict(row)
						else:
							for row in cursor:
								count += 1
								yield row

						logging.info(f"Recieved '{count}' results")

				# except psycopg2.errors.DeadlockDetected: # Another process is using that table
				# 	if (nested >= nested_max):
				# 		raise ValueError(error["message"], catalogue)

				# 	logging.info(f"Waiting 90 seconds then trying again ({nested + 1} of {nested_max} tries)")
				# 	time.sleep(90)
				# 	for item in yield_runSQL(queries, as_dict=as_dict, nested_max=nested_max, nested=nested + 1, **kwargs):
				# 		yield item
				# 	return
					
				except Exception as error:
					if (not PyUtilities.logger.debugging):
						logging.info(f"query_sql: '{query_sql}'")
						logging.info(f"query_args: '{query_args}'")
					raise error
					# traceback.print_exception(type(error), error, error.__traceback__)

def runSQL(*args, **kwargs):
	return tuple(yield_runSQL(*args, **kwargs))

def apply_stringIndex(frame, columnName, *, string_index__keepValue=False, connection=None):
	""" Replaces a string value with an id in the table string_index.
	Use this to make string columns a primary key in a table.

	string_index__keepValue (bool) - Determines if the value should not be removed
	
	Example Input: apply_stringIndex(frame, "lorem")
	Example Input: apply_stringIndex(frame, ("lorem", "ipsum"))
	Example Input: apply_stringIndex(frame, "lorem", string_index__keepValue=True)
	"""

	# Replace pk string columns with foreign key IDs
	columnList = PyUtilities.common.ensure_container(columnName)
	insert(
		data=PyUtilities.datasource.general.getUnique(frame, columnList, as_list=False),
		table="string_index",
		method="insert_ignore",
		reset_incrementer="id",
		connection=connection,
		log_table=False,
	)

	catalogue_index = {value: key for (key, value) in raw(query_sql="SELECT id, value FROM string_index", as_dict=False, connection=connection)}
	catalogue_index["nan"] = 0
	catalogue_index["None"] = 0

	for key in columnList:
		if (string_index__keepValue):
			frame[f"{key}__value"] = frame[key]

		frame[key] = frame[key].astype("str").replace(catalogue_index).astype("Int64")
		
	return columnList

def apply_foreign(frame, table, column=None, *, schema=None, fk=None, sameName=None, columnKeep=None, refresh_fk=False,
	remove=True, insert_fk=False, search_fk=None, method="upsert", upsert_constraint=None, reset_incrementer=None,
	fk_type=None, fk_rename=None, include_modifier=True, missing=None, connection=None, insert_method="single",
	modifyData=None, modifyData_insert=None, skip_null=True, drop_null=True, expand_user=None, expand_db=None):
	""" Takes *column* from *frame* and puts it into *table*, replacing it with a foreign key as *fk*.

	insert_fk (bool) - Determines if the inserted foreign key gets insrted back into the data or not
	remove (bool) - Determines if *column* should be removed from *frame* or not
	search_fk (list) - Which column(s) to use for determining what the fk is
	missing (dict) - A catalogue of what value to use if a value or column is missing
	refresh_fk (bool) - If the foreign key already exists if it shoudl be looked up anyways

	Example Input: apply_foreign(frame, table="sos")
	Example Input: apply_foreign(frame, table="sos", column="description")
	Example Input: apply_foreign(frame, table="sos", column={"sos_description": "description"})
	Example Input: apply_foreign(frame, table="sos", column="description", method="insert")
	Example Input: apply_foreign(frame, table="sos", column={"sos_description": "description"}, insert_fk=True)
	Example Input: apply_foreign(frame, table="division", column="name", columnKeep="company_id")
	Example Input: apply_foreign(frame, table="sos", column="description", remove=False)
	Example Input: apply_foreign(frame, table="listing", column="address_street", remove=False, method="select", fk_type="str")
	Example Input: apply_foreign(frame, table="sos", column=("code", "description"))
	Example Input: apply_foreign(frame, table="sos", column="code", method="select_insert_ignore")
	Example Input: apply_foreign(frame, table="sos", fk={"sos_new_id": "sos_id"})
	Example Input: apply_foreign(frame, table="site", expand_user={"address": { "street": "address_street", "zip": "address_zip" }})
	Example Input: apply_foreign(frame, table="site", expand_db={"address_street": True, "address_zipcode": "address ->> 'zip'"})
	Example Input: apply_foreign(frame, table="site", expand_db=("address_street", "address_zip"))
	Example Input: apply_foreign(frame, table="site", expand_db="address_zip")


	"address": { "street": "address_street", "zip": "address_zip" }})
	"""

	def parse__fk():
		nonlocal fk, table

		def getCatalogue():
			if (not fk):
				key = f"{table}_id"
				return {key: key}
			
			if (isinstance(fk, dict)):
				return fk
			
			catalogue = {}
			for key in PyUtilities.common.ensure_container(fk):
				catalogue.update(PyUtilities.common.ensure_dict(key or {}, useAsKey=None, convertContainer=True))

			return catalogue

		########################

		fkList__alias = getCatalogue()
		fkList__user, fkList__db = tuple(zip(*(fkList__alias.items()))) if fkList__alias else ((), ())
		return fkList__alias, list(fkList__user), list(fkList__db)

	def parse__column():
		nonlocal column

		def getCatalogue():
			if (isinstance(column, (tuple, list))):
				return {key: key for key in column}
			return PyUtilities.common.ensure_dict(column or {}, useAsKey=None, convertContainer=True)
		
		########################
		
		columnList__alias = getCatalogue()
		columnList__user, columnList__db = tuple(zip(*(columnList__alias.items()))) if columnList__alias else ((), ())
		return columnList__alias, list(columnList__user), list(columnList__db)

	def parse__search_fk():
		nonlocal search_fk, columnList__alias, columnList__user, columnList__db

		if (not search_fk):
			return columnList__alias, columnList__user, columnList__db

		if (PyUtilities.common.is_container(search_fk)):
			myList = list(search_fk)
			return dict(zip(myList, myList)), myList, myList

		search_fk__alias = PyUtilities.common.ensure_dict(search_fk, useAsKey=None, convertContainer=True)
		search_fk__user, search_fk__db = tuple(zip(*(search_fk__alias.items()))) if search_fk__alias else ((), ())
		return search_fk__alias, list(search_fk__user), list(search_fk__db)

	def parse__columnKeep():
		nonlocal columnKeep

		columnKeep__alias = PyUtilities.common.ensure_dict(columnKeep, useAsKey=None, convertContainer=True)
		columnKeep__user, columnKeep__db = tuple(zip(*(columnKeep__alias.items()))) if columnKeep__alias else ((), ())

		columnKeep__user = list(columnKeep__user)
		columnKeep__db = list(columnKeep__db)

		if (include_modifier and ("last_modifier" in frame.columns) and ("last_modifier" not in columnKeep__alias)):
			columnKeep__user.append("last_modifier")
			columnKeep__db.append("last_modifier")

		return columnKeep__alias, columnKeep__user, columnKeep__db

	def copyFrame():
		nonlocal frame, missing, fk_missing, fkList__user, columnList__user, columnKeep__user

		frame_expanded = frame
		if (expand_user):
			frame_expanded = frame.copy(deep=True)
			for (column_current, catalogue) in PyUtilities.common.ensure_dict(expand_user, useAsKey=None, convertContainer=True).items():
				column = frame_expanded[column_current]
				for (column_attribute, column_alias) in PyUtilities.common.ensure_dict(catalogue, useAsKey=None, convertContainer=True).items():
					frame_expanded[column_alias] = column.map(lambda item: item[column_attribute] or None)

		_columnList = [*set([*columnList__user, *columnKeep__user] if fk_missing else [*fkList__user, *columnList__user, *columnKeep__user])]
		if (missing):
			# Still raise an error if a key not in missing is not present, but don't for keys that are in missing
			_columnList = [item for item in _columnList if ((item in frame_expanded.columns) or (item not in missing))]

		return frame_expanded[_columnList].copy(deep=True)

	def do_filter():
		nonlocal frame_foreign, method, schema, table, connection, search_fk__user, search_fk__db

		if (not method.startswith("select_")):
			return

		method = method.split("select_")[1]

		# Get existing matches
		data_existing = raw(
			query_sql=f"SELECT DISTINCT {', '.join(search_fk__db)} FROM {schema}.{table}",
			as_dict=False, connection=connection
		)

		frame_existing = pandas.DataFrame(data_existing, columns=search_fk__user)

		# Filter out items that don't need to be inserted
		frame_filtered = frame_foreign.merge(frame_existing, on=search_fk__user, how="left", indicator=True)
		frame_filtered = frame_filtered.loc[(frame_filtered._merge == "left_only")]
		frame_filtered.drop("_merge", axis=1, inplace=True)

		frame_foreign = frame_filtered.drop_duplicates(subset=search_fk__user, keep="first").copy(deep=True)
		frame_foreign.dropna(subset=search_fk__user, inplace=True)

		if (frame_foreign.empty):
			logging.info("There are no new foreign items to add")
		else:
			logging.info(f"Doing '{method}' for {len(frame_foreign)} foreign items to {schema}.{table}")

	def do_insert():
		nonlocal frame, frame_foreign, method, schema, table, connection, upsert_constraint, reset_incrementer, fk_missing, sameName, columnList__alias, fkList__alias, fkList__user, modifyData_insert, skip_null

		def get_missingValue(_frame, key, value):
			nonlocal missingValue_id_catalogue

			if (PyUtilities.common.inspect.ismethod(value) or PyUtilities.common.inspect.isfunction(value)):
				def wrappedFunction(series):
					return value(series=series, frame=frame, key=key)

				#####################

				return wrappedFunction

			match (value):
				case "__UNIQUE__":
					def wrappedFunction(series):
						nonlocal missingValue_id_catalogue, existing

						_value = f"Unknown {missingValue_id_catalogue[key]}"
						while existing.get(_value):
							missingValue_id_catalogue[key] += 1
							_value = f"Unknown {missingValue_id_catalogue[key]}"

						existing[_value] = True
						return _value

					#####################

					existing = {key: True for key in _frame[key].to_list()}

					if (key not in missingValue_id_catalogue):
						missingValue_id_catalogue[key] = 1

					return wrappedFunction

			def wrappedFunction(series):
				return value

			#####################

			return wrappedFunction

		def apply_missing(_frame):
			for (key, value) in missing.items():
				if (key not in _frame.columns):
					_frame[key] = None

				_get_missingValue = get_missingValue(_frame, key, value)
				for i, series in _frame.iterrows():
					_frame.at[i, key] = _get_missingValue(series)

		def get_columnList():
			return [key for key in getColumns_constraint(PyUtilities.common.requiredArg(upsert_constraint, f"Missing *upsert_constraint* for {schema}.{table}"), table=table, schema=schema, connection=connection) if (key in frame_foreign.columns)]

		def apply_replace(column, catalogue):
			frame_foreign[column].replace(catalogue, inplace=True)
			frame[frame_foreign.columns] = frame[frame_foreign.columns].replace(catalogue)

		########################

		if (frame_foreign.empty or (method == "select")):
			return

		if (sameName):
			if (fk_missing):
				for column, catalogue_sameName in sameName.items():
					frame_foreign[column].replace(catalogue_sameName, inplace=True)
					frame[column] = frame[column].replace(catalogue_sameName)
			else:
				# Overwrite the correct foreign key(s) too
				sameList__user = [*fkList__user, *sameName.keys()]
				frame_sameName = frame_foreign[sameList__user].drop_duplicates(subset=sameList__user)

				catalogue_replaceFk = {}
				for (column, catalogue_sameName) in sameName.items():
					# Determine which columns to pull new fk values from
					frame_replaceFrom = frame_sameName.loc[frame_sameName[column].isin(catalogue_sameName.values())]
					frame_replaceFrom = frame_replaceFrom.rename({key: f"{key}___new" for key in fkList__user}, axis=1)
					frame_replaceTo = frame_sameName.loc[frame_sameName[column].isin(catalogue_sameName.keys())].replace(catalogue_sameName)
					
					# Apply the new fk values
					frame_combined = frame_replaceTo.merge(frame_replaceFrom, on=column, how="left", indicator=True)
					for _column in fkList__user:
						frame_combined[_column] = numpy.where(frame_combined._merge == "both", frame_combined[f"{_column}___new"], frame_combined[_column])

					# Do replacement
					frame_foreign[column].replace(catalogue_sameName, inplace=True)
					frame[frame_foreign.columns] = frame[frame_foreign.columns].replace(catalogue_sameName)

					for (index, row) in frame_combined.iterrows():
						for _column in fkList__user:
							logging.debug(f"Replace '{_column}' where '{column}' is equal to '{row[column]}' with '{row[_column]}'")
							frame_foreign.loc[frame_foreign[column] == f"{row[column]}", _column] = f"{row[_column]}"
							frame.loc[frame[column] == row[column], _column] = row[_column]

		columnList = None
		if (fk_missing):
			frame_foreign.rename(columnList__alias, axis=1, inplace=True)
			columnList = get_columnList()

			frame_foreign.drop_duplicates(subset=(columnList if columnList else None), inplace=True)
		else:
			# for frame_duplicates in PyUtilities.datasource.general.yield_duplicates(frame, ["property_name"]):
			# 	with pandas.option_context("display.max_rows", None, "display.max_columns", None):
			# 		print("@1", frame_duplicates)
			# 	dfddfsdsf

			frame_foreign.drop_duplicates(subset=fkList__user, inplace=True)
			frame_foreign.dropna(subset=fkList__user, inplace=True)
			frame_foreign.rename(fkList__alias, axis=1, inplace=True)
			frame_foreign.rename(columnList__alias, axis=1, inplace=True)

		if (missing):
			missingValue_id_catalogue = {}
			apply_missing(frame_foreign)

		if (modifyData_insert):
			logging.info("Modifying foreign data before insert...")
			for myFunction in PyUtilities.common.ensure_container(modifyData_insert):
				myFunction(frame_foreign)

		if (skip_null):
			# Only insert values that are not just pure null values
			frame_foreign = frame_foreign[PyUtilities.datasource.general.getNullColumns(frame_foreign, invert=True)]

		if (frame_foreign.empty):
			return

		if (drop_null):
			if (isinstance(drop_null, bool)):
				columnList = columnList or get_columnList()
				# with pandas.option_context("display.max_rows", None, "display.max_columns", None):
				# 	print(columnList)
				# 	print(frame_foreign)
				frame_foreign.dropna(subset=columnList, inplace=True)
			else:
				frame_foreign.dropna(subset=drop_null, inplace=True)

		# with pandas.option_context("display.max_rows", None, "display.max_columns", None):
		# 	print(frame_foreign)

		insert(
			data=frame_foreign,
			table=table,
			method=method,
			schema=schema,
			insert_method=insert_method,
			upsert_constraint=upsert_constraint,
			reset_incrementer=reset_incrementer,
			connection=connection,
		)

	def do_lookup():
		nonlocal frame, fk_missing, insert_fk, fk_type, fkList__alias, fkList__user, search_fk__alias, refresh_fk

		if ((not refresh_fk) and ((not fk_missing) or insert_fk)):
			return

		if (refresh_fk and (not fk_missing)):
			# Remove the foreign key from the frame and re-insert it
			frame.drop(fkList__alias, axis=1, inplace=True)

		fk_type = fk_type or {}
		if (isinstance(fk_type, str)):
			fk_type = { key: fk_type for key in fkList__user }

		catalogue_lookup = {}
		catalogue_lookup.update(fkList__alias)
		catalogue_lookup.update(search_fk__alias)

		if (expand_db):
			# {"address_street": True, "address_zipcode": "address ->> 'zip'"}
			for (key__user, key__db) in PyUtilities.common.ensure_dict(expand_db, defaultKey=True, useAsKey=True, convertContainer=True).items():
				if (key__db is True):
					generator = iter(key__user.split("_"))
					key__db = f'\"{next(generator, key__user)}\"'
					for value in generator:
						if (value):
							key__db += f" ->> '{value}'"

				catalogue_lookup[key__user] = key__db

		for (key__user, key__db) in catalogue_lookup.items():
			if (not key__db.startswith('\"')):
				catalogue_lookup[key__user] = f'\"{key__db}\"'

		# Get a lookup table for what index corresponds to which fk pair
		selectList = tuple(f'{key__db} as \"{key__user}\"' for (key__user, key__db) in catalogue_lookup.items())

		existing_raw = raw(
			query_sql=f"SELECT {', '.join(selectList)} FROM {schema}.{table}",
			as_dict=False,
			connection=connection,
		)
		catalogue_index = { tuple(args): key for (key, *args) in existing_raw } # TODO: Currently, this method assumes thre is only a single fk; Support composite keys

		# TODO: Support different types using 'fk_type'
		for key in fkList__user:
			frame[key] = [(catalogue_index.get(index) or None) for index in zip(*(frame[_key] for _key in search_fk__user))]
			
			match (fk_type.get(key, "int")):
				case "int":
					frame[key] = frame[key].fillna(0)
					frame[key] = frame[key].astype(float).astype("Int64")

				case "string" | "str":
					frame[key] = frame[key].astype(str)

				case _:
					raise KeyError(f"Unknown fk type for '{key}': {fk_type.get(key)}")

		# with pandas.option_context("display.max_rows", None, "display.max_columns", None):
		# 	print(frame["site_id"])
		# 	dsfsdfdd

	########################

	if (modifyData):
		logging.info("Modifying data during foreign TableUpdater.routine...")
		for myFunction in PyUtilities.common.ensure_container(modifyData):
			if (myFunction is not None):
				response = myFunction(frame)
				if (response is not None):
					frame = response

	schema = schema or "public"
	
	fkList__alias, fkList__user, fkList__db = parse__fk()
	fk_missing = all(key not in frame.columns for key in fkList__user)
	if (fk_missing):
		if (insert_fk or (not column)):
			raise ValueError(f"*frame* is missing at least 1 of these columns: {fkList__user}", frame.columns)

		if (not upsert_constraint):
			upsert_constraint = f"{table}_un"

	columnList__alias, columnList__user, columnList__db = parse__column()
	search_fk__alias, search_fk__user, search_fk__db = parse__search_fk()
	columnKeep__alias, columnKeep__user, columnKeep__db = parse__columnKeep()

	frame_foreign = copyFrame()
	do_filter()
	do_insert()
	do_lookup()

	if (remove):
		if (not isinstance(remove, bool)):
			frame.drop(list(key for key in PyUtilities.common.ensure_container(remove) if key not in columnKeep__user), axis=1, inplace=True)

		elif (len(columnList__alias)):
			frame.drop(list(key for key in columnList__alias if key not in columnKeep__user), axis=1, inplace=True)

	if (fk_rename):
		for [i, key] in enumerate(fkList__user):
			if (key in fk_rename):
				key_new = fk_rename[key]
				fkList__user[i] = key_new;
				frame.rename({key: key_new}, axis=1, inplace=True)

	return fkList__user

def getColumns(table, *, schema=None, remove=None, **kwargs):
	""" Returns the column names for a table.

	Example Input: getColumns("lorem")
	Example Input: getColumns("turnover", schema="report")
	Example Input: getColumns("lorem", remove=["date_created", "date_modified", "last_modifier", "modify_count"])
	"""

	return tuple(zip(*raw(f"""
		SELECT
			column_name
		FROM
			information_schema.columns
		WHERE
			(table_schema = '{schema or "public"}') AND
			(table_name   = '{table}') AND
			(column_name not in %s)
	""", (remove,), as_dict=False, **kwargs)))[0]


def getColumns_constraint(constraint, *, schema=None, table=None, **kwargs):
	""" Returns which columns a table's constraint belongs to

	Example Input: getColumns("lorem_un")
	"""

	sql_raw = f"""
		SELECT
			information_schema.key_column_usage.COLUMN_NAME
		FROM
			pg_constraint
			{"JOIN pg_namespace ON (pg_namespace.oid = pg_constraint.connamespace)" if schema else ""}
			JOIN information_schema.key_column_usage ON (information_schema.key_column_usage.constraint_name = pg_constraint.conname)
		WHERE
			(pg_constraint.conname = %s)
		"""
	query_args = [constraint]

	if (schema):
		sql_raw += " AND (pg_namespace.nspname = %s)"
		query_args.append(schema)

	if (table):
		sql_raw += " AND (information_schema.key_column_usage.table_name = %s)"
		query_args.append(table)

	answer = tuple(zip(*raw(sql_raw, query_args, as_dict=False, **kwargs)))

	if (not answer):
		raise ValueError(f"Cannot find constraint columns for {constraint}; schema: {schema}; table: {table}")

	return answer[0]

class TestCase(PyUtilities.testing.BaseCase):
	def test_Postgres_canInsert(self):
		with self.assertLogs(level="INFO"):
			frame = PyUtilities.datasource.general.get_frame(
				data=[{"a": 1, "b": 2}, {"a": 2, "b": 3}],
				input_type="csv",
			)

			with self.assertRaises(psycopg2.errors.UndefinedColumn):
				insert(
					data=frame,
					table="property",
					schema="main",
					method="upsert",
				)

if (__name__ == "__main__"):
	PyUtilities.testing.test()