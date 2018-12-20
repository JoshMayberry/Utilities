#This document is used to declare the attributes and methods for use on Cython.

#Include the C++ code from Container.cpp
cdef extern from "Container.cpp": #Note that this path that you specify is relative to the current file- not setup.py
	pass

#Declare a C++ class interface
cdef extern from "Container.h" namespace "shapes":
	#Declare class with cdef cppclass
	cdef cppclass Container:
		#Add public attributes
		Container() except + #Note that the constructor is declared as "except +". If the C++ code or the initial memory allocation raises an exception due to a failure, this will let Cython safely raise an appropriate Python exception instead (see below). Without this declaration, C++ exceptions originating from the constructor will not be handled by Cython.
		Container(int, int, int, int) except +
		int x0, y0, x1, y1
		int getArea()
		void getSize(int* width, int* height)
		void move(int, int)