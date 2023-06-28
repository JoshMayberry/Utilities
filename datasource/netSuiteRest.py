import os
import re
import sys
import logging
import functools
import contextlib
import urllib.parse

import netsuite

import PyUtilities.common
from PyUtilities.datasource.common import config

@contextlib.contextmanager
def getConnection(*args, connection=None, **kwargs):
	""" Retuns an object to use for connecting to NetSuite using REST.

	Example Input: getConnection()
	"""

	if (connection is not None):
		yield connection
		return

	_connection = NetSuiteConnection_REST(*args, **kwargs)
	with _connection:
		yield _connection

class NetSuiteConnection_REST():
	def __init__(self, connection_ns=None, *, nested_max=1, configKwargs=None,
		login_token=None, login_token_secret=None, login_consumer=None, login_consumer_secret=None, login_account=None, **kwargs):
		""" A helper object for working with NetSuite.

		Example Input: NetSuiteConnection()
		Example Input: NetSuiteConnection(connection_ns)
		"""

		self.skipLookup = {}
		self.nested_max = nested_max

		self.connection_ns = connection_ns
		self.connection_ns__given = self.connection_ns is not None

		self.login_token = login_token or config("token_id", "netsuite", **(configKwargs or {}))
		self.login_token_secret = login_token_secret or config("token_secret", "netsuite", **(configKwargs or {}))

		self.login_consumer = login_consumer or config("consumer_id", "netsuite", **(configKwargs or {}))
		self.login_consumer_secret = login_consumer_secret or config("consumer_secret", "netsuite", **(configKwargs or {}))

		self.login_account = login_account or config("account", "netsuite", **(configKwargs or {}))

	def __enter__(self):
		if (not self.connection_ns__given):
			self.connection_ns = self.getConnection()

		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if (not self.connection_ns__given):
			self.connection_ns = None

	@contextlib.contextmanager
	def getConnection(cls, *, _self=None, connection=None, configKwargs=None, 
		login_token=None, login_token_secret=None, login_consumer=None, login_consumer_secret=None, login_account=None, **kwargs):

		if (connection is not None):
			yield connection
			return

		logging.info("Opening NetSuite REST connection...")

		login_token = login_token or config("token_id", "netsuite", **(configKwargs or {}))
		login_token_secret = login_token_secret or config("token_secret", "netsuite", **(configKwargs or {}))

		login_consumer = login_consumer or config("consumer_id", "netsuite", **(configKwargs or {}))
		login_consumer_secret = login_consumer_secret or config("consumer_secret", "netsuite", **(configKwargs or {}))

		yield netsuite.NetSuite(netsuite.Config(
			account=self.login_account,
			auth=netsuite.TokenAuth(
				consumer_key=self.login_consumer,
				consumer_secret=self.login_consumer_secret,
				token_id=self.login_token,
				token_secret=self.login_token_secret,
			)
		))

	def set_skipLookup(self, value):
		""" Any keys that need toi be looked up that match whats given will not be pursued.

		Example Input: set_skipLookup(None)
		Example Input: set_skipLookup("addressBook")
		"""

		self.skipLookup = {} if (value is None) else {key: True for key in PyUtilities.common.ensure_container(value or None)}

	findEndpoint = re.compile(r"/record/v1/(.+)", re.IGNORECASE)
	
	@classmethod
	def _getEndpoint(cls, catalogue_link):
		href = catalogue_link["href"]
		endpoint = cls.findEndpoint.search(href)[1]
		if (not endpoint):
			raise ValueError(f"Cannot find endpoint from '{href}'")

		return endpoint

	def select(self, *args, **kwargs):
		return tuple(self.yield_select(*args, **kwargs))

	def query(self, *args, **kwargs):
		return tuple(self.yield_query(*args, **kwargs))

	def yield_query(self, *args, **kwargs):
		""" Yields data from the given query.

		Example Input: yield_query("SELECT email, COUNT(*) as count FROM Transactions GROUP BY email", limit=10)
		"""

		for item in self.yield_select(*args, is_query=True, **kwargs):
			yield item

	def yield_select(self, output_type, queryKwargs=None, *, is_query=False, **kwargs):
		""" Yields Data from the NetSuite API.
		See: https://jacobsvante.github.io/netsuite/
		See: https://system.netsuite.com/help/helpcenter/en_US/APIs/REST_API_Browser/record/v1/2022.2/index.html

		is_query (bool) - If *output_type* is actually an SQL query

		Example Input: yield_select("customer")
		Example Input: yield_select("customer", {"limit": 10})
		"""

		# noPermission = ['assemblyItem', 'inventoryItem', 'nonInventorySaleItem', 'subscriptionPlan']
		# noParam = ['cashSale', 'creditMemo', 'customer', 'customerSubsidiaryRelationship', 'employee', 'invoice', 'itemFulfillment', 'journalEntry', 'purchaseOrder', 'salesOrder', 'subsidiary', 'vendorBill']
		# yesParam = ['billingAccount', 'calendarEvent', 'charge', 'contact', 'contactCategory', 'contactRole', 'emailTemplate', 'message', 'phoneCall', 'priceBook', 'pricePlan', 'subscription', 'subscriptionChangeOrder', 'subscriptionLine', 'subscriptionPlan', 'subscriptionTerm', 'task', 'timeBill', 'usage', 'vendor', 'vendorSubsidiaryRelationship']
		# needsBeta = ['account', 'accountingBook', 'accountingContext', 'accountingPeriod', 'advIntercompanyJournalEntry', 'allocationSchedule', 'amortizationSchedule', 'amortizationTemplate', 'assemblyBuild', 'assemblyUnbuild', 'billingClass', 'billingRateCard', 'billingRevenueEvent', 'billingSchedule', 'bin', 'binTransfer', 'binWorksheet', 'blanketPurchaseOrder', 'bom', 'bomRevision', 'bonus', 'budgetExchangeRate', 'bulkOwnershipTransfer', 'campaign', 'campaignResponse', 'campaignTemplate', 'cardholderAuthentication', 'cashRefund', 'chargeRule', 'check', 'classification', 'cmscontent', 'cmscontenttype', 'commerceCategory', 'competitor', 'consolidatedExchangeRate', 'costCategory', 'couponCode', 'creditCardCharge', 'creditCardRefund', 'currency', 'customerCategory', 'customerDeposit', 'customerMessage', 'customerPayment', 'customerPaymentAuthorization', 'customerRefund', 'customerStatus', 'department', 'deposit', 'depositApplication', 'descriptionItem', 'discountItem', 'downloadItem', 'employeeExpenseSourceType', 'entityAccountMapping', 'estimate', 'expenseCategory', 'expenseReport', 'expenseReportPolicy', 'fairValuePrice', 'fixedAmountProjectRevenueRule', 'fulfillmentRequest', 'genericResource', 'giftCertificate', 'giftCertificateItem', 'globalAccountMapping', 'globalInventoryRelationship', 'importedEmployeeExpense', 'inboundShipment', 'intercompanyJournalEntry', 'intercompanyTransferOrder', 'inventoryAdjustment', 'inventoryCostRevaluation', 'inventoryCount', 'inventoryNumber', 'inventoryStatus', 'inventoryStatusChange', 'inventoryTransfer', 'issue', 'issueProduct', 'itemAccountMapping', 'itemDemandPlan', 'itemGroup', 'itemLocationConfiguration', 'itemReceipt', 'itemRevision', 'itemSupplyPlan', 'job', 'jobStatus', 'jobType', 'kitItem', 'laborBasedProjectRevenueRule', 'location', 'manufacturingCostTemplate', 'manufacturingOperationTask', 'manufacturingRouting', 'markupItem', 'merchandiseHierarchyLevel', 'merchandiseHierarchyNode', 'merchandiseHierarchyVersion', 'nexus', 'nonInventoryPurchaseItem', 'nonInventoryResaleItem', 'note', 'noteType', 'opportunity', 'orderReservation', 'otherChargePurchaseItem', 'otherChargeResaleItem', 'otherChargeSaleItem', 'otherName', 'otherNameCategory', 'partner', 'partnerCategory', 'paycheck', 'paycheckJournal', 'paymentItem', 'paymentMethod', 'payrollItem', 'pctCompleteProjectRevenueRule', 'periodEndJournal', 'plannedOrder', 'planningItemCategory', 'planningItemGroup', 'planningRuleGroup', 'planningView', 'priceLevel', 'pricingGroup', 'projectExpenseType', 'projectIcChargeRequest', 'projectTask', 'projectTemplate', 'promotionCode', 'purchaseContract', 'purchaseRequisition', 'receiveInboundShipment', 'resourceAllocation', 'returnAuthorization', 'revRecSchedule', 'revRecTemplate', 'revenueArrangement', 'revenueCommitment', 'revenueCommitmentReversal', 'revenuePlan', 'salesChannel', 'salesRole', 'salesTaxItem', 'servicePurchaseItem', 'serviceResaleItem', 'serviceSaleItem', 'shipItem', 'solution', 'statisticalJournalEntry', 'storePickupFulfillment', 'subtotalItem', 'supplyChainSnapshot', 'supplyChainSnapshotSimulation', 'supplyChangeOrder', 'supplyPlanDefinition', 'supportCase', 'taxAcct', 'taxGroup', 'taxPeriod', 'taxType', 'term', 'timeEntry', 'timeSheet', 'topic', 'transferOrder', 'unitsType', 'vendorCategory', 'vendorCredit', 'vendorPayment', 'vendorReturnAuthorization', 'webSite', 'workOrder', 'workOrderClose', 'workOrderCompletion', 'workOrderIssue', 'workplace']

		queryKwargs = {**(queryKwargs or {})}

		endpoint = output_type
		if (not is_query):
			match (output_type):
				# No Params Needed
				case "cashSale" | "creditMemo" | "customer" | "customerSubsidiaryRelationship" | "employee" | "invoice" | "itemFulfillment" | "journalEntry" | "purchaseOrder" | "salesOrder" | "subsidiary" | "vendorBill":
					pass

				# Beta Needed
				case "account" | "accountingBook" | "accountingContext" | "accountingPeriod" | "advIntercompanyJournalEntry" | "allocationSchedule" | "amortizationSchedule" | "amortizationTemplate" | "assemblyBuild" | "assemblyUnbuild" | "billingClass" | "billingRateCard" | "billingRevenueEvent" | "billingSchedule" | "bin" | "binTransfer" | "binWorksheet" | "blanketPurchaseOrder" | "bom" | "bomRevision" | "bonus" | "budgetExchangeRate" | "bulkOwnershipTransfer" | "campaign" | "campaignResponse" | "campaignTemplate" | "cardholderAuthentication" | "cashRefund" | "chargeRule" | "check" | "classification" | "cmscontent" | "cmscontenttype" | "commerceCategory" | "competitor" | "consolidatedExchangeRate" | "costCategory" | "couponCode" | "creditCardCharge" | "creditCardRefund" | "currency" | "customerCategory" | "customerDeposit" | "customerMessage" | "customerPayment" | "customerPaymentAuthorization" | "customerRefund" | "customerStatus" | "department" | "deposit" | "depositApplication" | "descriptionItem" | "discountItem" | "downloadItem" | "employeeExpenseSourceType" | "entityAccountMapping" | "estimate" | "expenseCategory" | "expenseReport" | "expenseReportPolicy" | "fairValuePrice" | "fixedAmountProjectRevenueRule" | "fulfillmentRequest" | "genericResource" | "giftCertificate" | "giftCertificateItem" | "globalAccountMapping" | "globalInventoryRelationship" | "importedEmployeeExpense" | "inboundShipment" | "intercompanyJournalEntry" | "intercompanyTransferOrder" | "inventoryAdjustment" | "inventoryCostRevaluation" | "inventoryCount" | "inventoryNumber" | "inventoryStatus" | "inventoryStatusChange" | "inventoryTransfer" | "issue" | "issueProduct" | "itemAccountMapping" | "itemDemandPlan" | "itemGroup" | "itemLocationConfiguration" | "itemReceipt" | "itemRevision" | "itemSupplyPlan" | "job" | "jobStatus" | "jobType" | "kitItem" | "laborBasedProjectRevenueRule" | "location" | "manufacturingCostTemplate" | "manufacturingOperationTask" | "manufacturingRouting" | "markupItem" | "merchandiseHierarchyLevel" | "merchandiseHierarchyNode" | "merchandiseHierarchyVersion" | "nexus" | "nonInventoryPurchaseItem" | "nonInventoryResaleItem" | "note" | "noteType" | "opportunity" | "orderReservation" | "otherChargePurchaseItem" | "otherChargeResaleItem" | "otherChargeSaleItem" | "otherName" | "otherNameCategory" | "partner" | "partnerCategory" | "paycheck" | "paycheckJournal" | "paymentItem" | "paymentMethod" | "payrollItem" | "pctCompleteProjectRevenueRule" | "periodEndJournal" | "plannedOrder" | "planningItemCategory" | "planningItemGroup" | "planningRuleGroup" | "planningView" | "priceLevel" | "pricingGroup" | "projectExpenseType" | "projectIcChargeRequest" | "projectTask" | "projectTemplate" | "promotionCode" | "purchaseContract" | "purchaseRequisition" | "receiveInboundShipment" | "resourceAllocation" | "returnAuthorization" | "revRecSchedule" | "revRecTemplate" | "revenueArrangement" | "revenueCommitment" | "revenueCommitmentReversal" | "revenuePlan" | "salesChannel" | "salesRole" | "salesTaxItem" | "servicePurchaseItem" | "serviceResaleItem" | "serviceSaleItem" | "shipItem" | "solution" | "statisticalJournalEntry" | "storePickupFulfillment" | "subtotalItem" | "supplyChainSnapshot" | "supplyChainSnapshotSimulation" | "supplyChangeOrder" | "supplyPlanDefinition" | "supportCase" | "taxAcct" | "taxGroup" | "taxPeriod" | "taxType" | "term" | "timeEntry" | "timeSheet" | "topic" | "transferOrder" | "unitsType" | "vendorCategory" | "vendorCredit" | "vendorPayment" | "vendorReturnAuthorization" | "webSite" | "workOrder" | "workOrderClose" | "workOrderCompletion" | "workOrderIssue" | "workplace":
					pass

				# Permission Needed
				case "assemblyItem" | "inventoryItem" | "nonInventorySaleItem" | "subscriptionPlan":
					pass

				# Params Needed
				# See: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1545222128.html
				case "billingAccount":
					queryKwargs["q"] = ""
					pass

				case "calendarEvent":
					pass

				case "charge":
					pass

				case "contact":
					pass

				case "contactCategory":
					pass

				case "contactRole":
					pass

				case "emailTemplate":
					pass

				case "message":
					pass

				case "phoneCall":
					pass

				case "priceBook":
					pass

				case "pricePlan":
					pass

				case "subscription":
					pass

				case "subscriptionChangeOrder":
					pass

				case "subscriptionLine":
					pass

				case "subscriptionTerm":
					pass

				case "task":
					pass

				case "timeBill":
					pass

				case "usage":
					pass

				case "vendor":
					pass

				case "vendorSubsidiaryRelationship":
					pass

				case _:
					raise KeyError(f"Unknown report name {output_type}")

		for item in self.yield_raw(endpoint, queryKwargs=queryKwargs, is_query=is_query, **kwargs):
			yield item

	def yield_raw(self, endpoint, queryKwargs=None, *, limit=None, nested_max=None, is_query=False, nested=-1, simplify=True, **kwargs):
		""" Yields data from the given endpoint.
		Can handle paginated results.

		is_query (bool) - If *endpoint* is actually an SQL query

		Example Input: yield_raw("customer")
		Example Input: yield_raw("customer", limit=3)
		Example Input: yield_raw("customer", {"limit": 10})
		Example Input: yield_raw("customer/4394")
		Example Input: yield_raw("SELECT email, COUNT(*) as count FROM transaction GROUP BY email", is_query=True)
		"""

		def yield_formattedKeyValue(answer):
			if (not simplify):
				return answer

			for (key, value) in answer.items():
				if (not isinstance(value, dict)):
					yield (key, value)
					continue

				if ("_children" in value):
					childList = value["_children"]
					if (not childList):
						yield (key, None)
						continue

					raise NotImplementedError("Simplify non-empty *_children*", value)

				if ("refName" in value):
					yield (key, value["refName"])
					continue

				raise NotImplementedError("Unknown Simplification Route", value)

		#######################
		
		nested += 1
		if (nested > (nested_max or self.nested_max)):
			return

		offset = 0
		count_yielded = 0

		hasMore = True
		while hasMore:
			logging.info(f"Getting '{endpoint}' from NetSuite" + (f"; nested: {nested}" if nested else ""))
			if (not is_query):
				result = self._makeRequest(endpoint, **(queryKwargs or {}), offset=offset)
			else:
				result = self._makeQuery(endpoint, **(queryKwargs or {}), offset=offset)

			if ("items" not in result):
				answer = self._expandResult(result, nested=nested, nested_max=nested_max, **kwargs)
				answer.pop("links", None)
				yield dict(yield_formattedKeyValue(answer))
				return

			totalResults = result["totalResults"]
			if (not totalResults):
				return

			offset += result.get("count", None) or len(result["items"])
			hasMore = result.get("hasMore", False)
			
			logging.info(f"Got links for {offset} of {totalResults} items for '{endpoint}'");

			if (is_query):
				for item in result["items"]:
					item.pop("links", [])
					yield item

					count_yielded +=1
					if (limit and (count_yielded >= limit)):
						return
				continue

			# Account for getting a list of links to look up
			for item in result["items"]:
				if ("links" not in item):
					raise NotImplementedError(f"Expected links to be in item; item: '{item}'; result: '{result}'")

				for catalogue_link in item.pop("links", []):
					endpoint_sub = self._getEndpoint(catalogue_link)
					for itemSub in self.yield_raw(endpoint_sub, nested=nested, nested_max=nested_max, **kwargs):
						yield dict(yield_formattedKeyValue(itemSub))

						count_yielded +=1
						if (limit and (count_yielded >= limit)):
							return

	@functools.lru_cache(maxsize=128)
	def _makeQuery(self, sql_raw, *, limit=100, offset=0, **kwargs):
		""" Sends a SuiteQL query to NetSuite.
		See: https://youtu.be/QM0wDvvrcaM?t=931
		See: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_157909186990.html
		See: https://system.netsuite.com/app/recordscatalog/rcbrowser.nl
		"""

		logging.info(f"Sending rest query to NetSuite")

		return PyUtilities.common.syncRunAsync(self.connection_ns.rest_api.suiteql(q=sql_raw, limit=limit, offset=offset))

	@functools.lru_cache(maxsize=128)
	def _makeRequest(self, endpoint, *, offset=0, **queryKwargs):
		""" Sends a GET request to NetSuite.
		Uses caching to prevent lookups that return redundant information
		"""

		_queryKwargs = {**queryKwargs}

		if (offset):
			_queryKwargs["offset"] = offset

		url = f"/record/v1/{endpoint}?" + urllib.parse.urlencode(_queryKwargs)

		logging.info(f"Sending '{url}' to NetSuite")

		try:
			return PyUtilities.common.syncRunAsync(self.connection_ns.rest_api.get(url))
		except Exception as error:
			match (getattr(error, "status_code")):
				case 403:
					logging.error(f"Missing permission to access endpoint '{endpoint}'; {error.response_text}")
					return

				case _:
					raise error

	def _expandResult(self, result, **kwargs):
		""" Returns the result with any needed lookups permormed. """

		answer = {}
		for (key, catalogue) in result.items():
			if (isinstance(catalogue, dict)):
				linkList = catalogue.pop("links", None)
				if ((linkList is not None) and (key not in self.skipLookup)):
					children = []
					catalogue["_children"] = children

					for catalogue_link in linkList:
						endpoint_sub = self._getEndpoint(catalogue_link)
						for child in self.yield_raw(endpoint_sub, **kwargs):
							children.append(child)
			
			answer[key] = catalogue

		return answer


if (__name__ == "__main__"):
	PyUtilities.logger.logger_info()

	with getConnection() as connection:

		# result = connection.query(r"""SELECT email, COUNT(*) as count FROM transaction GROUP BY email""", use_odbc=False, {"limit": 10}, limit=30, connection=connection)
		result = connection.query("""
			SELECT
				tl.unique_key AS UniqueKey,
				a.type_name AS TypeName,
				a.name AS AccountName,
				t.Trandate,
				tl.Subsidiary_Id,
				t.Status,
				t.Transaction_Type,
				a.AccountNumber,
				t.Transaction_Number,
				tl.Amount,
				t.date_last_modified,
				t.created_by_id
			FROM
				Transactions AS t,
				Transaction_lines AS tl ,
				Accounts AS a
			WHERE 
				t.transaction_id = tl.transaction_id AND 
				t.trandate BETWEEN ('2023-02-01') AND ('2023-02-28') AND 
				a.account_id = tl.account_id AND 
				tl.non_posting_line = 'No' AND
				a.type_name in ('Income','Other Income','Expense','Other Expense','Cost of Goods Sold')
		""")
		
		print("@0", result)
		
		for item in ['billingAccount', 'calendarEvent', 'charge', 'contact', 'contactCategory', 'contactRole', 'emailTemplate', 'message', 'phoneCall', 'priceBook', 'pricePlan', 'subscription', 'subscriptionChangeOrder', 'subscriptionLine', 'subscriptionTerm', 'task', 'timeBill', 'usage', 'vendor', 'vendorSubsidiaryRelationship']:
			logging.info(f"@1.1 {item}")
			try:
				result = connection.select(item, {"limit": 1}, limit=1, connection=connection)
				logging.info(f"@1.2 {result}")
			except Exception as error:
				logging.error(error)

			# break