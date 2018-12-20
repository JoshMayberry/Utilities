import types
import unittest
import warnings

import Utilities as MyUtilities

#Controller
class TestController(unittest.TestCase):

	#Setup
	@classmethod
	def setUpClass(cls):
		#See: https://stackoverflow.com/questions/879173/how-to-ignore-deprecation-warnings-in-python/879249#879249
		warnings.simplefilter("ignore", category = DeprecationWarning)

	@classmethod
	def tearDownClass(cls):
		warnings.simplefilter("default", category = DeprecationWarning)

	def setUp(self):
		pass

	def tearDown(self):
		pass

	#Test Functions
	def test_ensure_container(self):
		def test():
			yield 1
			yield 2

		class Test():
			def __iter__(self):
				return iter((1, 2, 3))

		################################	

		ensure_container = MyUtilities.common.ensure_container

		#Basic Usage
		self.assertEqual(ensure_container(1), (1,))
		self.assertEqual(ensure_container((1,)), (1,))

		#Convert None
		self.assertEqual(ensure_container(None), ())
		self.assertEqual(ensure_container(None, convertNone = False), (None,))

		#Use For None
		self.assertEqual(ensure_container(0), (0,))
		self.assertEqual(ensure_container(0, useForNone = 0), ())

		#Consume Generators
		self.assertEqual(ensure_container((x for x in range(1, 3))), (1, 2))

		handle = test()
		self.assertEqual(ensure_container(handle), (1, 2))
		self.assertEqual(ensure_container(handle, evaluateGenerator = False), (handle,))

		#Don't consume functions
		self.assertEqual(ensure_container(test), (test,))

		#Args Support
		self.assertEqual(ensure_container(1, 2, 3), (1, 2, 3))
		self.assertEqual(ensure_container([1, 2], 3), (1, 2, 3))

		#Element Criteria
		##Single
		self.assertEqual(ensure_container((255, 255, 0)), (255, 255, 0))
		self.assertEqual(ensure_container((255, 255), elementCriteria = (3, int)), (255, 255))
		self.assertEqual(ensure_container((255, 255, 0), elementCriteria = (3, int)), ((255, 255, 0),))
		self.assertEqual(ensure_container((255, 255, 0, 255), elementCriteria = (3, int)), (255, 255, 0, 255))

		##Multiple
		self.assertEqual(ensure_container((255, 255), elementCriteria = ((3, int), (4, int))), (255, 255))
		self.assertEqual(ensure_container((255, 255, 0, 255), elementCriteria = ((3, int), (4, int))), ((255, 255, 0, 255),))
		self.assertEqual(ensure_container((255, 255, 0), elementCriteria = ((3, int), (4, int))), ((255, 255, 0),))

		#Element Types
		handle = Test()
		self.assertEqual(ensure_container(handle), (1, 2, 3))
		self.assertEqual(ensure_container(handle, elementTypes = (Test,)), (handle,))

	def test_ensure_functionInput(self):
		def lorem(): 
			pass

		def ipsum(): 
			pass

		################################

		ensure_functionInput = MyUtilities.common.ensure_functionInput

		#Basic Usage
		self.assertIsInstance(ensure_functionInput(lorem, myFunctionArgs = 1), types.GeneratorType)
		self.assertEqual(tuple(ensure_functionInput(lorem, myFunctionArgs = 1)), ((lorem, (1,), {}),))

		#Passing in args and kwargs differently
		self.assertEqual(tuple(ensure_functionInput(lorem, myFunctionArgs = (1, 2), myFunctionKwargs = {"x": 3})), tuple(ensure_functionInput(lorem, 1, 2, x = 3)))
		self.assertEqual(tuple(ensure_functionInput(lorem, myFunctionArgs = (1, 2), myFunctionKwargs = {"x": 3})), tuple(ensure_functionInput(lorem, 1, myFunctionArgs = 2, x = 3)))

		#Syntax for 'myFunction' as single item list
		self.assertEqual(tuple(ensure_functionInput(lorem, myFunctionArgs = None)), tuple(ensure_functionInput([lorem], myFunctionArgs = [None])))
		self.assertEqual(tuple(ensure_functionInput(lorem, myFunctionArgs = [None])), tuple(ensure_functionInput([lorem], myFunctionArgs = [[None]])))
		self.assertEqual(tuple(ensure_functionInput(lorem, myFunctionArgs = [1, 2, 3])), tuple(ensure_functionInput([lorem], myFunctionArgs = [[1, 2, 3]])))

		#Multiple functions
		self.assertEqual(tuple(ensure_functionInput([lorem, ipsum], myFunctionArgs = (1, 2))), ((lorem, (1,), {}), (ipsum, (2,), {})))
		self.assertEqual(tuple(ensure_functionInput([lorem, ipsum], myFunctionArgs = (None, 2))), ((lorem, (), {}), (ipsum, (2,), {})))
		self.assertEqual(tuple(ensure_functionInput([lorem, ipsum], myFunctionArgs = (None, None))), ((lorem, (), {}), (ipsum, (), {})))
		self.assertEqual(tuple(ensure_functionInput([lorem, ipsum], myFunctionArgs = ((1, 2, 3), None), myFunctionKwargs = (None, {"dolor": 1}))), ((lorem, (1, 2, 3), {}), (ipsum, (), {'dolor': 1})))

		#Error Catching
		self.assertEqual(tuple(ensure_functionInput([lorem], myFunctionArgs = [[1, 2, 3]])), ((lorem, (1, 2, 3), {}),))
		self.assertRaises(SyntaxError, lambda: tuple(ensure_functionInput([lorem], myFunctionArgs = [1, 2, 3])))

	def test_runMyFunction(self):
		def lorem(x):
			return 2

		def ipsum(x):
			raise CustomError()

		def dolor(error):
			return 3

		class CustomError(Exception):
			pass

		#############################

		runMyFunction = MyUtilities.common.runMyFunction

		#Basic Usage
		self.assertEqual(runMyFunction(lorem, 1), 2)

		#Error Catching
		self.assertRaises(CustomError, lambda: runMyFunction(ipsum, 1))
		self.assertEqual(runMyFunction(ipsum, 1, errorFunction = dolor), 3)


if __name__ == '__main__':
	unittest.main()
