# pylint: skip-file

import os
import re
import sys
import datetime

import numpy
import pandas
import collections

import pyad.adquery
import pyad.pyadutils

#Required Modules
	#pip install pyad

class IncorrectFormatError(Exception):
	""" Summaries should follow this format: '[direction] [part number] (' """
	pass

class ActiveDirectoryAPI():
	""" Connects to Active Directory to run queries.

	Example Use: 
		controller = ActiveDirectoryAPI()
		for row in controller.yieldQueryResult():
			print(row)
	"""

	all_attributes = { "accountExpires", "accountNameHistory", "aCSPolicyName", "adminCount", "adminDescription", "adminDisplayName", "altSecurityIdentities", "assistant", "attributeCertificateAttribute", "audio", "badPasswordTime", "badPwdCount", "businessCategory", "c", "carLicense", "catalogs", "cn", "co", "codePage", "comment", "company", "controlAccessRights", "countryCode", "dBCSPwd", "defaultClassStore", "defaultLocalPolicyObject", "department", "departmentNumber", "description", "desktopProfile", "destinationIndicator", "displayName", "displayNamePrintable", "distinguishedName", "division", "dNSHostName", "dSASignature", "dSCorePropagationData", "dynamicLDAPserver", "employeeID", "employeeNumber", "employeeType", "extensionName", "facsimileTelephoneNumber", "flags", "garbageCollPeriod", "gecos", "generationQualifier", "givenName", "groupMembershipSAM", "groupPriority", "groupsToIgnore", "homeDirectory", "homeDrive", "homePhone", "homePostalAddress", "houseIdentifier", "info", "initials", "instanceType", "internationalISDNNumber", "ipHostNumber", "ipPhone", "isCriticalSystemObject", "isDeleted", "isRecycled", "l", "labeledURI", "lastKnownParent", "lastLogoff", "lastLogon", "lastLogonTimestamp", "legacyExchangeDN", "lmPwdHistory", "localeID", "localPolicyFlags", "location", "lockoutTime", "loginShell", "logonCount", "logonHours", "logonWorkstation", "machineRole", "mail", "managedBy", "manager", "maxStorage", "mhsORAddress", "middleName", "mobile", "msCOM-UserPartitionSetLink", "msDRM-IdentityCertificate", "msDS-AdditionalDnsHostName", "msDS-AdditionalSamAccountName", "msDS-AllowedToActOnBehalfOfOtherIdentity", "msDS-AllowedToDelegateTo", "msDS-AssignedAuthNPolicy", "msDS-AssignedAuthNPolicySilo", "msDS-Cached-Membership", "msDS-Cached-Membership-Time-Stamp", "msDS-CloudAnchor", "msDS-cloudExtensionAttribute1", "msDS-cloudExtensionAttribute2", "msDS-cloudExtensionAttribute3", "msDS-cloudExtensionAttribute4", "msDS-cloudExtensionAttribute5", "msDS-cloudExtensionAttribute6", "msDS-cloudExtensionAttribute7", "msDS-cloudExtensionAttribute8", "msDS-cloudExtensionAttribute9", "msDS-cloudExtensionAttribute10", "msDS-cloudExtensionAttribute11", "msDS-cloudExtensionAttribute12", "msDS-cloudExtensionAttribute13", "msDS-cloudExtensionAttribute14", "msDS-cloudExtensionAttribute15", "msDS-cloudExtensionAttribute16", "msDS-cloudExtensionAttribute17", "msDS-cloudExtensionAttribute18", "msDS-cloudExtensionAttribute19", "msDS-cloudExtensionAttribute20", "mS-DS-ConsistencyChildCount", "mS-DS-ConsistencyGuid", "mS-DS-CreatorSID", "msDS-ExecuteScriptPassword", "msDS-ExternalDirectoryObjectId", "msDS-FailedInteractiveLogonCount", "msDS-FailedInteractiveLogonCountAtLastSuccessfulLogon", "msDS-GenerationId", "msDS-GeoCoordinatesAltitude", "msDS-GeoCoordinatesLatitude", "msDS-GeoCoordinatesLongitude", "msDS-HABSeniorityIndex", "msDS-HostServiceAccount", "msDS-KeyCredentialLink", "msDS-KrbTgtLink", "msDS-LastFailedInteractiveLogonTime", "msDS-LastKnownRDN", "msDS-LastSuccessfulInteractiveLogonTime", "msDS-NcType", "msDS-NeverRevealGroup", "msDS-ObjectSoa", "msDS-PhoneticCompanyName", "msDS-PhoneticDepartment", "msDS-PhoneticDisplayNAme", "msDS-PhoneticFirstName", "msDS-PhoneticLastName", "msDS-PrimaryComputer", "msDS-PromotionSettings", "msDS-RevealedUsers", "msDS-RevealOnDemandGroup", "msDS-SecondaryKrbTgtNumber", "msDS-Site-Affinity", "msDS-SourceAnchor", "msDS-SourceObjectDN", "msDS-SupportedEncryptionTypes", "msDS-SyncServerUrl", "msExchAssistantName", "msExchHouseIdentifier", "msExchLabeledURI", "msIIS-FTPDir", "msIIS-FTPRoot", "msImaging-HashAlgorithm", "msImaging-ThumbprintHash", "mSMQDigests", "mSMQDigestsMig", "msNPCallingStationID", "msNPSavedCallingStationID", "msPKIAccountCredentials", "msPKI-CredentialRoamingTokens", "msPKIDPAPIMasterKeys", "msPKIRoamingTimeStamp", "msRADIUSCallbackNumber", "msRADIUS-FramedInterfaceId", "msRADIUSFramedIPAddress", "msRADIUS-FramedIpv6Prefix", "msRADIUS-FramedIpv6Route", "msRADIUSFramedRoute", "msRADIUS-SavedFramedInterfaceId", "msRADIUS-SavedFramedIpv6Prefix", "msRADIUSServiceType", "msSFU30Aliases", "msSFU30Name", "msSFU30NisDomain", "msTPM-OwnerInformation", "msTPM-TpmInformationForComputer", "msTSAllowLogon", "msTSBrokenConnectionAction", "msTSConnectClientDrives", "msTSConnectPrinterDrives", "msTSDefaultToMainPrinter", "msTSEndpointData", "msTSEndpointPlugin", "msTSEndpointType", "msTSExpireDate", "msTSExpireDate2", "msTSExpireDate3", "msTSExpireDate4", "msTSHomeDirectory", "msTSHomeDrive", "msTSInitialProgram", "msTSLicenseVersion", "msTSLicenseVersion2", "msTSLicenseVersion3", "msTSLicenseVersion4", "msTSLSProperty01", "msTSLSProperty02", "msTSManagingLS", "msTSManagingLS2", "msTSManagingLS3", "msTSManagingLS4", "msTSMaxConnectionTime", "msTSMaxDisconnectionTime", "msTSMaxIdleTime", "msTSPrimaryDesktop", "msTSProfilePath", "msTSProperty01", "msTSProperty02", "msTSReconnectionAction", "msTSRemoteControl", "msTSSecondaryDesktops", "msTSWorkDirectory", "name", "netbootDUID", "netbootGUID", "netbootInitialization", "netbootMachineFilePath", "netbootSIFFile", "networkAddress", "nisMapName", "ntPwdHistory", "o", "objectCategory", "objectClass", "objectGUID", "objectSid", "objectVersion", "operatingSystem", "operatingSystemHotfix", "operatingSystemServicePack", "operatingSystemVersion", "operatorCount", "otherFacsimileTelephoneNumber", "otherHomePhone", "otherIpPhone", "otherLoginWorkstations", "otherMailbox", "otherMobile", "otherPager", "otherTelephone", "otherWellKnownObjects", "ou", "pager", "partialAttributeDeletionList", "partialAttributeSet", "personalTitle", "photo", "physicalDeliveryOfficeName", "physicalLocationObject", "policyReplicationFlags", "postalAddress", "postalCode", "postOfficeBox", "preferredDeliveryMethod", "preferredLanguage", "preferredOU", "primaryGroupID", "primaryTelexNumber", "profilePath", "proxiedObjectName", "proxyAddresses", "pwdLastSet", "registeredAddress", "replPropertyMetaData", "replUpToDateVector", "repsFrom", "repsTo", "revision", "rid", "rIDSetReferences", "roomNumber", "sAMAccountName", "sAMAccountType", "scriptPath", "secretary", "securityIdentifier", "seeAlso", "serialNumber", "servicePrincipalName", "shadowExpire", "shadowFlag", "shadowInactive", "shadowLastChange", "shadowMax", "shadowMin", "shadowWarning", "showInAddressBook", "showInAdvancedViewOnly", "sIDHistory", "siteGUID", "sn", "st", "street", "streetAddress", "subRefs", "supplementalCredentials", "systemFlags", "telephoneNumber", "teletexTerminalIdentifier", "telexNumber", "terminalServer", "textEncodedORAddress", "thumbnailLogo", "thumbnailPhoto", "title", "uid", "uidNumber", "unixHomeDirectory", "unixUserPassword", "url", "userAccountControl", "userCert", "userCertificate", "userParameters", "userPassword", "userPKCS12", "userPrincipalName", "userSharedFolder", "userSharedFolderOther", "userSMIMECertificate", "userWorkstations", "uSNChanged", "uSNCreated", "uSNDSALastObjRemoved", "USNIntersite", "uSNLastObjRem", "uSNSource", "volumeCount", "wbemPath", "wellKnownObjects", "whenChanged", "whenCreated", "wWWHomePage", "x121Address", "x500uniqueIdentifier"}
	misspelled_attributes: { "fSMORoleOwnder", "gridNumber", "ipegPhoto", "msDS-AuthenticatedAltDC", "mSMGSignCertificates", "mSMGSignCertificatesMig", "msNPAllowDailin", "msRADIUS-SavedIpv6Route", "msRASSSavedCallbackNumber", "msRASSSavedFramedIPAddress", "msRASSSavedFramedRoute", "primaryInternationalSDNNumber", "unicodePws"}
	used_attributes = {'displayName', 'localPolicyFlags', 'cn', 'badPwdCount', 'ipPhone', 'homeDirectory', 'dNSHostName', 'lockoutTime', 'logonHours', 'instanceType', 'countryCode', 'location', 'dSCorePropagationData', 'accountExpires', 'l', 'isCriticalSystemObject', 'initials', 'mobile', 'company', 'givenName', 'comment', 'description', 'homeDrive', 'codePage', 'lastLogonTimestamp', 'localeID', 'extensionName', 'dSASignature', 'lastLogoff', 'lastLogon', 'badPasswordTime', "description", 'logonCount', 'flags', 'adminCount', 'mail', 'department', 'msDS-NcType', 'mSMQDigests', 'msDS-SupportedEncryptionTypes', 'msDS-KeyCredentialLink', 'objectCategory', 'postalCode', 'operatingSystemServicePack', 'otherWellKnownObjects', 'postOfficeBox', 'objectSid', 'objectClass', 'primaryGroupID', 'operatingSystemVersion', 'operatingSystem', 'objectGUID', 'physicalDeliveryOfficeName', 'ou', 'name', 'whenChanged', 'title', 'replUpToDateVector', 'pwdLastSet', 'scriptPath', 'uSNCreated', 'userWorkstations', 'sn', 'userParameters', 'sAMAccountType', 'showInAdvancedViewOnly', 'rIDSetReferences', 'systemFlags', 'userAccountControl', 'whenCreated', 'streetAddress', 'repsFrom', 'wellKnownObjects', 'telephoneNumber', 'url', 'servicePrincipalName', 'revision', 'subRefs', 'sIDHistory', 'st', 'repsTo', 'sAMAccountName', 'userPrincipalName', 'uSNChanged'}

	def yieldQueryResult(self, *args, commonName = None, objectClass = None, filterDict = None, filterNone = True, include_groups = True):
		""" Yields results form an Active Directory query

		Example Input: yieldQueryResult()
		Example Input: yieldQueryResult(filterNone = False)
		Example Input: yieldQueryResult("displayName", "mail", objectClass = "person")
		Example Input: yieldQueryResult(["displayName", "cn"], "mail", objectClass = "person")
		Example Input: yieldQueryResult(["displayName", "cn"], "mail", objectClass = { "exact": "person", "not": "computer" })
		Example Input: yieldQueryResult(["displayName", "cn"], "mail", objectClass = { "exact": "person", "not": ["computer", "organizationalUnit"] })
		"""

		def yield_whereClause():
			format_value = {
				"exact": lambda key, value: f"{key} = '{value}'",
				"like": lambda key, value: f"{key} like '{value}'",
				"not": lambda key, value: f"{key} <> '{value}'",
			}

			def getValue(key, value):
				if (isinstance(value, str)):
					return f"{key} = '{value}'"
				
				def yieldValue():
					for formatKey, newValue in value.items():
						if (formatKey not in format_value):
							raise KeyError(f"Unknown format key '{formatKey}'");

						if (isinstance(newValue, str)):
							newValue = (newValue,)

						for item in newValue:
							yield format_value[formatKey](key, item)

				####################################

				return f" {value.get('join', 'and')} ".join(yieldValue())

			####################################

			if (commonName != None):
				yield getValue("CN", commonName)

			if (objectClass != None):
				yield getValue("objectClass", objectClass)

			if (filterDict != None):
				for key, value in filterDict.items():
					yield getValue(key, value)

		def yield_attributes():
			yield "distinguishedName"

			# Will crash if there are more than 100 attributes in the list
			for item in args or self.used_attributes:
				if (isinstance(item, (list, tuple))):
					backupCatalogue[item[0]] = item[1:]
					exclude.update(item[1:])
					yield from item
				else:
					yield item

		def yield_answer():
			convert_datetime = lambda x: None if (x is None) else pyad.pyadutils.convert_datetime(x)
			convert_timespan = lambda x: None if (x is None) else pyad.pyadutils.convert_timespan(x)
			convert_bigint = lambda x: None if (x is None) else pyad.pyadutils.convert_bigint(x)
			convert_guid = lambda x: None if (x is None) else pyad.pyadutils.convert_guid(x)
			convert_sid = lambda x: None if (x is None) else pyad.pyadutils.convert_sid(x)

			def convert_logonHours(value):
				# See: https://social.technet.microsoft.com/Forums/exchange/en-US/545552d4-8daf-4dd8-8291-6f088f35c2a4/how-is-the-logon-hours-attribute-set-in-active-directory-windows-server-2008-r2-?forum=winserverDS
				if (value is None):
					return None

				totalHours = 0
				for shift_1, shift_2, shift_3 in zip(*[iter(value.tobytes())]*3):
					totalHours += len((format(shift_1, '08b') + format(shift_2, '08b') + format(shift_3, '08b')).replace("0", ""))
				return totalHours

			def convert_instanceType(value):
				# See: https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-ada1/3c95bace-a9bd-4227-9c32-de1015d2bcd2
				if (value is None):
					return None

				return {
					1: "The head of naming context",
					2: "This replica is not instantiated",
					3: "The object is writable on this directory",
					4: "The naming context above this one on this directory is held",
					5: "The naming context is being constructed for the first time via replication",
					6: "The naming context is being removed from the local directory system agent (DSA)",
				}[value]

			def convert_datetime__from_pywintype(value):
				# See: https://stackoverflow.com/questions/39028290/python-convert-pywintyptes-datetime-to-datetime-datetime/57366132#57366132
				return pandas.Timestamp(value.timestamp(), unit = 's');

			format_value = {
				"pwdLastSet": convert_datetime,
				"lastLogon": convert_datetime,
				"lastLogoff": convert_datetime,
				"lastLogonTimestamp": convert_datetime,
				"objectGUID": convert_guid,
				"objectSid": convert_sid,
				"uSNCreated": convert_bigint,
				"uSNChanged": convert_bigint,
				"accountExpires": convert_timespan,
				"badPasswordTime": convert_datetime,
				"lockoutTime": convert_datetime,
				"logonHours": convert_logonHours,
				"instanceType": convert_instanceType,
				"whenCreated": convert_datetime__from_pywintype,
				"whenChanged": convert_datetime__from_pywintype,
				"isCriticalSystemObject": lambda x: None if (x is None) else int(x),
			}

			def getValue(row, key, value):
				if (value == None):
					if (key in backupCatalogue):
						for newKey in backupCatalogue[key]:
							passed, newValue = getValue(row, newKey, row.get(newKey, None))
							if (passed):
								return True, newValue

					if (filterNone):
						return False, None

				if (key in exclude):
					return False, None

				if (key in format_value):
					value = format_value[key](value)

				return True, value

			def yield_dict(row):
				if (include_groups):
					group_list = []
					if ("distinguishedName" not in args):
						distinguishedName = row.pop("distinguishedName", None)
					else:
						distinguishedName = row.get("distinguishedName", None)
					
					if (distinguishedName):
						for item in distinguishedName.split(","):
							key, value = item.split("=")
							if (key == "OU"):
								group_list.append(value)

					yield "group_list", group_list

				elif ("distinguishedName" not in args):
					row.pop("distinguishedName", None)

				for key, value in row.items():
					passed, newValue = getValue(row, key, value)
					if (passed):
						yield key, newValue

			####################################

			for row in query.get_results():
				yield dict(yield_dict(row))

		####################################

		backupCatalogue = {}
		exclude = set()
		attributeList = tuple(yield_attributes())

		query = pyad.adquery.ADQuery()
		query.reset()

		where_clause = " and ".join(yield_whereClause())

		query.execute_query(
			attributes = attributeList,
			where_clause = where_clause,
			base_dn = "DC=DMTE,DC=Local"
		)

		yield from yield_answer()

	def yieldUsers(self, **kwargs):
		yield from self.yieldQueryResult(
			("displayName", "name", "cn"),
			"homeDirectory", "mail",

			"logonCount", "lastLogoff", "lastLogon", "logonHours",
			"lockoutTime", "badPasswordTime", "pwdLastSet", "badPwdCount",
			"whenCreated", "whenChanged",

			objectClass = { "exact": "person", "not": "computer" }, **kwargs)
		# yield from self.yieldQueryResult(objectClass = { "exact": "person", "not": "computer" }, **kwargs)

	def yieldComputer(self, **kwargs):
		yield from self.yieldQueryResult(
			("displayName", "name", "cn"),
			"operatingSystem", "operatingSystemVersion", "dNSHostName", "description", "location",

			"logonCount", "lastLogoff", "lastLogon", "logonHours",
			"lockoutTime", "badPasswordTime", "pwdLastSet", "badPwdCount",
			"whenCreated", "whenChanged",

			objectClass = "computer", **kwargs)

	def yieldNode(self, **kwargs):
		yield from self.yieldQueryResult(
			"name",
			"whenCreated", "whenChanged",

			objectClass = "dnsNode", **kwargs)

	def yieldAll(self, *args, **kwargs):
		yield from self.yieldQueryResult(*args, **kwargs)

	def dundasConversion(self, functionName, *, expand_groups = True, filterNone = False, **kwargs):
		""" Converts the output to a format Dundas BI can understand

		Example Use: dundasConversion("yieldUsers")
		Example Use: dundasConversion("yieldUsers", filterNone = True)
		Example Use: dundasConversion("yieldUsers", expand_groups = False, include_groups = False)
		"""

		def yield_row():
			myFunction = getattr(self, functionName, None)
			if (myFunction == None):
				raise KeyError(f"Invalid Function name {functionName}")

			if (not expand_groups):
				yield from myFunction(filterNone = filterNone, **kwargs)
				return

			for row in myFunction(filterNone = filterNone, **kwargs):
				group_list = row.pop("group_list", None) or []

				if (not group_list):
					yield {**row, "group": None}
					continue

				for group in group_list:
					yield {**row, "group": group}

		####################################

		# answer = pandas.DataFrame(yield_row())
		# answer = answer.where(pandas.notnull(answer), None)
		# return pandas.json_normalize(tuple(yield_row()))
		return pandas.json_normalize(yield_row())

if (__name__ == "__main__"):
	controller = ActiveDirectoryAPI()
	# for item in controller.yieldNode():
	# 	print(item)
	# 	print()
	# print(controller.dundasConversion("yieldUsers"))

	for item in controller.yieldQueryResult("mail", objectClass = { "exact": "person", "not": "computer" }, filterDict = { "comment": { "exact": "1581" } }):
		print(item)
		print()
