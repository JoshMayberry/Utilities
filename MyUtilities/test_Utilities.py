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
		ensure_container = MyUtilities.common.ensure_container
		
		def test():
			yield 1
			yield 2

		class Test():
			def __iter__(self):
				return iter((1, 2, 3))

		################################	

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
		ensure_functionInput = MyUtilities.common.ensure_functionInput
		
		def lorem(): 
			pass

		def ipsum(): 
			pass

		################################

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
		runMyFunction = MyUtilities.common.runMyFunction
	
		def lorem(x):
			return 2

		def ipsum(x):
			raise CustomError()

		def dolor(error):
			return 3

		class CustomError(Exception):
			pass

		#############################

		#Basic Usage
		self.assertEqual(runMyFunction(lorem, 1), 2)

		#Error Catching
		self.assertRaises(CustomError, lambda: runMyFunction(ipsum, 1))
		self.assertEqual(runMyFunction(ipsum, 1, errorFunction = dolor), 3)

	# def test_makeHook(self):
	# 	makeHook = MyUtilities.common.makeHook

	# 	#Basic Usage
	# 	@makeHook("ipsum", "Append", "SetSelection")
	# 	class Lorem():
	# 		def __init__(self):
	# 			self.ipsum = Ipsum()

	# 	class Ipsum():
	# 		def Append(self, x):
	# 			return (x, 1)

	# 		def SetSelection(self, x):
	# 			return (x, 2)

	# 	########################################

	# 	self.assertEqual(tuple(item for item in dir(Lorem) if (not item.startswith("__"))), ('Append', 'SetSelection'))

	# 	lorem = Lorem()

	# 	self.assertEqual(lorem.Append(1), (1, 1))
	# 	self.assertEqual(lorem.Append(1), (1, 1))
	# 	self.assertEqual(lorem.Append(1), (1, 1))
	# 	self.assertEqual(lorem.SetSelection(1), (1, 2))
	# 	self.assertEqual(lorem.SetSelection(1), (1, 2))
	# 	self.assertEqual(lorem.SetSelection(1), (1, 2))
	# 	self.assertEqual(lorem.Append(1), lorem.ipsum.Append(1))

	# 	#Nested Usage
	# 	@makeHook("ipsum.dolor", "Append", "SetSelection")
	# 	class Lorem():
	# 		def __init__(self):
	# 			self.ipsum = Ipsum()

	# 	class Ipsum():
	# 		def __init__(self):
	# 			self.dolor = Dolor()

	# 	class Dolor():
	# 		def Append(self, x):
	# 			return (x, 1)

	# 		def SetSelection(self, x):
	# 			return (x, 2)

	# 	lorem = Lorem()

	# 	self.assertEqual(lorem.Append(1), (1, 1))
	# 	self.assertEqual(lorem.Append(1), (1, 1))
	# 	self.assertEqual(lorem.Append(1), (1, 1))
	# 	self.assertEqual(lorem.SetSelection(1), (1, 2))
	# 	self.assertEqual(lorem.SetSelection(1), (1, 2))
	# 	self.assertEqual(lorem.SetSelection(1), (1, 2))
	# 	self.assertEqual(lorem.Append(1), lorem.ipsum.dolor.Append(1))

	def test_CustomIterator(self):
		CustomIterator = MyUtilities.common.CustomIterator

		class Test():
			def __init__(self):
				self.lorem = [1, 2, 3, 4]

		################################

		test = Test()
		lorem = CustomIterator(test, "lorem")

		self.assertEqual(lorem.next(), 1)
		self.assertEqual(lorem.next(), 2)
		self.assertEqual(lorem.next(), 3)
		self.assertEqual(lorem.previous(), 2)
		self.assertEqual(lorem.next(), 3)
		self.assertEqual(lorem.next(), 4)

	def test_makeProperty(self):
		makeProperty = MyUtilities.common.makeProperty

		#Basic Usage
		class Test():
			@makeProperty()
			class lorem():
				def getter(self):
					return self.ipsum
				def setter(self, value):
					self.ipsum = value + 2

		test = Test()
		self.assertRaises(AttributeError, lambda: test.lorem)
		test.lorem = 3
		self.assertEqual(test.lorem, 5)

		#Default Value
		class Test():
			@makeProperty(default = 7)
			class lorem():
				def getter(self):
					return self.ipsum
				def setter(self, value):
					self.ipsum = value + 2

		test = Test()
		self.assertEqual(test.lorem, 9)

		#Type Annotations
		##Basic Use
		class Test():
			@makeProperty(forceType = True)
			class lorem():
				def getter(self):
					return self.ipsum
				def setter(self, value: int):
					self.ipsum = value

		test = Test()
		test.lorem = 3
		self.assertRaises(TypeError, lambda: setattr(test, "lorem", "3"))
		self.assertEqual(test.lorem, 3)

		##Auto Casting
		class Test():
			@makeProperty(forceType = True, convertType = True)
			class lorem():
				def getter(self):
					return self.ipsum
				def setter(self, value: int):
					self.ipsum = value

		test = Test()
		test.lorem = "3"
		self.assertEqual(test.lorem, 3)

		##Manual Casting
		def formatter(value):
			return int(value) + 2
				
		class Test():
			@makeProperty(forceType = True, convertType = formatter)
			class lorem():
				def getter(self):
					return self.ipsum
				def setter(self, value: int):
					self.ipsum = value

		test = Test()
		test.lorem = "3"
		self.assertEqual(test.lorem, 5)

if __name__ == '__main__':
	unittest.main()
