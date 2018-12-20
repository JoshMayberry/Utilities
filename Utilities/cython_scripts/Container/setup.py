#Tutorial From: https://pythonprogramming.net/introduction-and-basics-cython-tutorial/

#Required Modules
##py -m pip install
  # cython

#Required software
  # Visual C++ Build Tools 2015
  	# - https://blogs.msdn.microsoft.com/pythonengineering/2016/04/11/unable-to-find-vcvarsall-bat/
  	# - http://go.microsoft.com/fwlink/?LinkId=691126

#See: https://stackoverflow.com/questions/16993927/using-cython-to-link-python-to-a-shared-library

import sys
import distutils.core
import Cython.Build

sys.argv.append("build_ext")
sys.argv.append("--inplace")

#See: https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#cythonize-arguments
distutils.core.setup(
  name = 'c_Container',
  ext_modules = Cython.Build.cythonize(module_list = "c_Container.pyx"),
)

