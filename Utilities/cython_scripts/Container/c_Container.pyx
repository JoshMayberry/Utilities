#cython: language_level=3
#distutils: language = c++

#Tutorial: https://cython.readthedocs.io/en/latest/src/userguide/wrapping_CPlusPlus.html

from Container cimport Container

cpdef is_container(item):
	raise NotImplementedError()

#See: https://cython.readthedocs.io/en/latest/src/tutorial/cdef_classes.html
#See: https://cython.readthedocs.io/en/latest/src/userguide/early_binding_for_speed.html
cdef class PyContainer:
	cdef Container*c_rect  # Needed to use __dealloc__

	def __cinit__(self, int x0, int y0, int x1, int y1):
		self.c_rect = new Container(x0, y0, x1, y1)

	def __dealloc__(self):
		del self.c_rect

	def get_area(self):
		return self.c_rect.getArea()

	def get_size(self):
		cdef int width, height
		self.c_rect.getSize(&width, &height)
		return width, height

	def move(self, dx, dy):
		self.c_rect.move(dx, dy)

	# Attribute access
	@property
	def x0(self):
		return self.c_rect.x0
	@x0.setter
	def x0(self, x0):
		self.c_rect.x0 = x0

	# Attribute access
	@property
	def x1(self):
		return self.c_rect.x1
	@x1.setter
	def x1(self, x1):
		self.c_rect.x1 = x1

	# Attribute access
	@property
	def y0(self):
		return self.c_rect.y0
	@y0.setter
	def y0(self, y0):
		self.c_rect.y0 = y0

	# Attribute access
	@property
	def y1(self):
		return self.c_rect.y1
	@y1.setter
	def y1(self, y1):
		self.c_rect.y1 = y1