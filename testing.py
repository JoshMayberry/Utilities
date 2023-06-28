import PyUtilities.common
import unittest

class BaseCase(unittest.TestCase):
	pass

def test(TestCase):
	""" Runs the given container of *TestCase* in unittest.
	See: https://stackoverflow.com/questions/19087189/python-unittest-testcase-object-has-no-attribute-runtest/19087974#19087974

	Example Input: test(TestCase)
	Example Input: test((TestCase_1, TestCase_2))
	"""

	suite = unittest.TestSuite()
	for item in PyUtilities.common.ensure_container(TestCase):
		suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(item))
	unittest.TextTestRunner().run(suite)