# -*- coding:utf-8 -*-
import unittest as real_unittest
import time
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import get_app, get_apps
from django.test import _doctest as doctest
from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.testcases import OutputChecker, DocTestRunner, TestCase
from django.utils import unittest

from colorama import init
from django.utils.unittest import suite

init()
from colorama import Fore, Back, Style

try:
    all
except NameError:
    from django.utils.itercompat import all


__all__ = ('DjangoTestRunner', 'DjangoTestSuiteRunner', 'run_tests')

# The module name for tests outside models.py
TEST_MODULE = 'tests'

doctestOutputChecker = OutputChecker()

class DjangoTestRunner(unittest.TextTestRunner):
    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "DjangoTestRunner is deprecated; it's functionality is indistinguishable from TextTestRunner",
            PendingDeprecationWarning
        )
        super(DjangoTestRunner, self).__init__(*args, **kwargs)

def get_tests(app_module):
    try:
        # 格式如: api.models
        app_path = app_module.__name__.split('.')[:-1]

        # 导入api.tests.py这样的modules
        test_module = __import__('.'.join(app_path + [TEST_MODULE]), {}, {}, TEST_MODULE)
    except ImportError, e:
        # Couldn't import tests.py. Was it due to a missing file, or
        # due to an import error in a tests.py that actually exists?
        import os.path
        from imp import find_module
        try:
            mod = find_module(TEST_MODULE, [os.path.dirname(app_module.__file__)])
        except ImportError:
            # 'tests' module doesn't exist. Move on.
            test_module = None
        else:
            # The module exists, so there must be an import error in the
            # test module itself. We don't need the module; so if the
            # module was a single file module (i.e., tests.py), close the file
            # handle returned by find_module. Otherwise, the test module
            # is a directory, and there is nothing to close.
            if mod[0]:
                mod[0].close()
            raise
    return test_module

def build_suite(app_module):
    "Create a complete Django test suite for the provided application module"

    # 如何从app中读取所有的Test呢?
    suite = unittest.TestSuite()

    # Load unit and doctests in the models.py module. If module has
    # a suite() method, use it. Otherwise build the test suite ourselves.
    if hasattr(app_module, 'suite'):
        suite.addTest(app_module.suite())
    else:
        # 如何从app_module中加载Test呢?
        #
        # suite可以套嵌 TestSuit
        #
        suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(app_module))

        try:
            suite.addTest(doctest.DocTestSuite(app_module,
                                               checker=doctestOutputChecker,
                                               runner=DocTestRunner))
        except ValueError:
            # No doc tests in models.py
            pass

    # Check to see if a separate 'tests' module exists parallel to the
    # models module
    # 正常的Django Test
    # 从 api.tests中读取Test
    test_module = get_tests(app_module)
    if test_module:
        # Load unit and doctests in the tests.py module. If module has
        # a suite() method, use it. Otherwise build the test suite ourselves.
        if hasattr(test_module, 'suite'):
            suite.addTest(test_module.suite())
        else:
            # 1. 正常TestCase的导入
            # 每一个定义的TestCase最终都实例化成为
            test_suite = unittest.defaultTestLoader.loadTestsFromModule(test_module)

            # app的label如何识别呢?
            # app +
            #
            for item in test_suite:
                # item 为test_suite, 对应一个TestCase
                if isinstance(item, unittest.TestSuite):
                    # "api" + "." + "TestWeibo"
                    test_case_class = ""
                    for test_suite in item:
                        test_case_class = test_suite.__class__.__name__
                        break

                    add_full_test_name_2_testsuit(item, test_module.__package__ + "." + test_case_class)
            suite.addTest(test_suite)
            try:
                suite.addTest(doctest.DocTestSuite(test_module,
                                                   checker=doctestOutputChecker,
                                                   runner=DocTestRunner))
            except ValueError:
                # No doc tests in tests.py
                pass
    return suite

def build_test(label):
    """Construct a test case with the specified label. Label should be of the
    form model.TestClass or model.TestClass.test_method. Returns an
    instantiated test or test suite corresponding to the label provided.

    """
    parts = label.split('.')
    # 两层
    # api.TestWeibo
    # api.TestWeibo.test_post_method
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError("Test label '%s' should be of the form app.TestCase or app.TestCase.test_method" % label)

    #
    # First, look for TestCase instances with a name that matches
    #
    app_module = get_app(parts[0])
    test_module = get_tests(app_module)

    # 获取TestClass?
    TestClass = getattr(app_module, parts[1], None)

    # 为什么优先考虑 models.py呢?
    # Couldn't find the test class in models.py; look in tests.py
    if TestClass is None:

        # tests.py
        if test_module:
            TestClass = getattr(test_module, parts[1], None)

    try:
        if issubclass(TestClass, (unittest.TestCase, real_unittest.TestCase)):
            # 处理全部的TestClass
            if len(parts) == 2: # label is app.TestClass
                try:
                    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestClass)
                    add_full_test_name_2_testsuit(test_suite, label)
                    return test_suite
                except TypeError:
                    raise ValueError("Test label '%s' does not refer to a test class" % label)
            else: # label is app.TestClass.test_method
                # 处理当个的Test
                test = TestClass(parts[2])
                add_full_test_name_2_test(test, label)
                return test
    except TypeError:
        # TestClass isn't a TestClass - it must be a method or normal class
        pass

    #
    # If there isn't a TestCase, look for a doctest that matches
    #
    tests = []
    for module in app_module, test_module:
        try:
            doctests = doctest.DocTestSuite(module,
                                            checker=doctestOutputChecker,
                                            runner=DocTestRunner)
            # Now iterate over the suite, looking for doctests whose name
            # matches the pattern that was given
            for test in doctests:
                if test._dt_test.name in (
                        '%s.%s' % (module.__name__, '.'.join(parts[1:])),
                        '%s.__test__.%s' % (module.__name__, '.'.join(parts[1:]))):
                    tests.append(test)
        except ValueError:
            # No doctests found.
            pass

    # If no tests were found, then we were given a bad test label.
    if not tests:
        raise ValueError("Test label '%s' does not refer to a test" % label)

    # Construct a suite out of the tests that matched.
    return unittest.TestSuite(tests)

def partition_suite(suite, classes, bins):
    """
    Partitions a test suite by test type.

    classes is a sequence of types
    bins is a sequence of TestSuites, one more than classes

    Tests of type classes[i] are added to bins[i],
    tests with no match found in classes are place in bins[-1]
    """
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            partition_suite(test, classes, bins)
        else:
            for i in range(len(classes)):
                if isinstance(test, classes[i]):
                    bins[i].addTest(test)
                    break
            else:
                bins[-1].addTest(test)

def reorder_suite(suite, classes):
    """
    Reorders a test suite by test type.

    classes is a sequence of types

    All tests of type clases[0] are placed first, then tests of type classes[1], etc.
    Tests with no match in classes are placed last.
    """
    class_count = len(classes)
    bins = [unittest.TestSuite() for i in range(class_count+1)]
    partition_suite(suite, classes, bins)
    for i in range(class_count):
        bins[0].addTests(bins[i+1])
    return bins[0]

def _isnotsuite(test):
    "A crude way to tell apart testcases and suites with duck-typing"
    try:
        iter(test)
    except TypeError:
        return True
    return False

def dependency_ordered(test_databases, dependencies):
    """Reorder test_databases into an order that honors the dependencies
    described in TEST_DEPENDENCIES.
    """
    ordered_test_databases = []
    resolved_databases = set()
    while test_databases:
        changed = False
        deferred = []

        while test_databases:
            signature, (db_name, aliases) = test_databases.pop()
            dependencies_satisfied = True
            for alias in aliases:
                if alias in dependencies:
                    if all(a in resolved_databases for a in dependencies[alias]):
                        # all dependencies for this alias are satisfied
                        dependencies.pop(alias)
                        resolved_databases.add(alias)
                    else:
                        dependencies_satisfied = False
                else:
                    resolved_databases.add(alias)

            if dependencies_satisfied:
                ordered_test_databases.append((signature, (db_name, aliases)))
                changed = True
            else:
                deferred.append((signature, (db_name, aliases)))

        if not changed:
            raise ImproperlyConfigured("Circular dependency in TEST_DEPENDENCIES")
        test_databases = deferred
    return ordered_test_databases

def traverse_test_suit(suit):
    count = 0
    for t in suit:
        if isinstance(t, unittest.TestSuite):
            count += traverse_test_suit(t)
        else:
            count += 1
    return count

def add_full_test_name_2_test(test, label):
    """
        suite_or_test:
        可能为TestCase, 则需要为testcase添加一个test_name, base_package中已经包含了app, TestCase等信息，需要在最后面补充当前的Test的方法名
    """
    if isinstance(test, unittest.TestCase):
        test.test_name = label
def add_full_test_name_2_testsuit(suit, label):
    for item in suit:
        if isinstance(item, unittest.TestCase):
            item.test_name = label + "." + item._testMethodName





class DjangoTestSuiteRunner(object):
    def __init__(self, verbosity=1, interactive=True, failfast=True, **kwargs):
        self.verbosity = verbosity
        self.interactive = interactive
        self.failfast = failfast

    def setup_test_environment(self, **kwargs):
        setup_test_environment()
        settings.DEBUG = False

        # 处理处理中断信号?
        unittest.installHandler()

    def build_suite(self, test_labels, extra_tests=None, **kwargs):

        # 构建TestSuite
        suite = unittest.TestSuite()

        if test_labels:
            # labels如何处理呢?
            for label in test_labels:
                if '.' in label:
                    # python manage.py test api.TestAAA
                    suite.addTest(build_test(label))
                else:
                    # 当个app
                    # python manage.py test api
                    app = get_app(label) # 格式如: api.models
                    suite.addTest(build_suite(app))
        else:
            # 遍历每一个app
            for app in get_apps():
                suite.addTest(build_suite(app))

        if extra_tests:
            for test in extra_tests:
                suite.addTest(test)

        return reorder_suite(suite, (TestCase,))

    def setup_databases(self, **kwargs):
        from django.db import connections, DEFAULT_DB_ALIAS

        # First pass -- work out which databases actually need to be created,
        # and which ones are test mirrors or duplicate entries in DATABASES
        mirrored_aliases = {}
        test_databases = {}
        dependencies = {}

        # 如何准备数据库呢?
        for alias in connections:
            connection = connections[alias]
            if connection.settings_dict['TEST_MIRROR']:
                # If the database is marked as a test mirror, save
                # the alias.
                mirrored_aliases[alias] = connection.settings_dict['TEST_MIRROR']
            else:
                # Store a tuple with DB parameters that uniquely identify it.
                # If we have two aliases with the same values for that tuple,
                # we only need to create the test database once.
                # 获取测试数据的配置
                item = test_databases.setdefault(
                    connection.creation.test_db_signature(),
                    (connection.settings_dict['NAME'], [])
                )

                # 为数据库添加 alias
                item[1].append(alias)

                if 'TEST_DEPENDENCIES' in connection.settings_dict:
                    dependencies[alias] = connection.settings_dict['TEST_DEPENDENCIES']
                else:
                    if alias != DEFAULT_DB_ALIAS:
                        dependencies[alias] = connection.settings_dict.get('TEST_DEPENDENCIES', [DEFAULT_DB_ALIAS])

        # Second pass -- actually create the databases.
        old_names = []
        mirrors = []
        for signature, (db_name, aliases) in dependency_ordered(test_databases.items(), dependencies):
            # Actually create the database for the first connection
            connection = connections[aliases[0]]
            old_names.append((connection, db_name, True))

            # 创建测试数据库
            test_db_name = connection.creation.create_test_db(self.verbosity, autoclobber=not self.interactive)

            for alias in aliases[1:]:
                connection = connections[alias]
                if db_name:
                    old_names.append((connection, db_name, False))
                    connection.settings_dict['NAME'] = test_db_name
                else:
                    # If settings_dict['NAME'] isn't defined, we have a backend where
                    # the name isn't important -- e.g., SQLite, which uses :memory:.
                    # Force create the database instead of assuming it's a duplicate.
                    old_names.append((connection, db_name, True))
                    connection.creation.create_test_db(self.verbosity, autoclobber=not self.interactive)

        for alias, mirror_alias in mirrored_aliases.items():
            mirrors.append((alias, connections[alias].settings_dict['NAME']))
            connections[alias].settings_dict['NAME'] = connections[mirror_alias].settings_dict['NAME']

        return old_names, mirrors

    def run_suite(self, suite, **kwargs):
        # 遍历TestSuite

        # 准备做测试
        total_count = traverse_test_suit(suite)

        # 直接注入
        from unittest import case
        case.test_case_current_index = 0
        case.test_case_total_count = total_count

        return unittest.TextTestRunner(verbosity=self.verbosity, failfast=self.failfast, resultclass=CYTextTestResult).run(suite)

    def teardown_databases(self, old_config, **kwargs):
        from django.db import connections
        old_names, mirrors = old_config
        # Point all the mirrors back to the originals
        for alias, old_name in mirrors:
            connections[alias].settings_dict['NAME'] = old_name
        # Destroy all the non-mirror databases
        for connection, old_name, destroy in old_names:
            if destroy:
                connection.creation.destroy_test_db(old_name, self.verbosity)
            else:
                connection.settings_dict['NAME'] = old_name

    def teardown_test_environment(self, **kwargs):
        unittest.removeHandler()
        teardown_test_environment()

    def suite_result(self, suite, result, **kwargs):
        return len(result.failures) + len(result.errors)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        """
        Run the unit tests for all the test labels in the provided list.
        Labels must be of the form:
         - app.TestClass.test_method
            Run a single specific test method
         - app.TestClass
            Run all the test methods in a given class
         - app
            Search for doctests and unittests in the named application.

        When looking for tests, the test runner will look in the models and
        tests modules for the application.

        A list of 'extra' tests may also be provided; these tests
        will be added to the test suite.

        Returns the number of tests that failed.
        """
        # 如何运行Test?
        self.setup_test_environment()

        # 1. 首先准备 test suite
        suite = self.build_suite(test_labels, extra_tests)

        old_config = self.setup_databases()

        # 3. 运行test suit
        result = self.run_suite(suite)


        self.teardown_databases(old_config)
        self.teardown_test_environment()
        return self.suite_result(suite, result)

def run_tests(test_labels, verbosity=1, interactive=True, failfast=False, extra_tests=None):
    import warnings
    warnings.warn(
        'The run_tests() test runner has been deprecated in favor of DjangoTestSuiteRunner.',
        DeprecationWarning
    )
    test_runner = DjangoTestSuiteRunner(verbosity=verbosity, interactive=interactive, failfast=failfast)
    return test_runner.run_tests(test_labels, extra_tests=extra_tests)


class CYTextTestResult(unittest.TextTestResult):

    def printErrorList(self, flavour, errors):
        """
            最后汇总，输出测试的结果:
        """
        for test, err in errors:
            self.stream.writeln(self.separator1)
            self.stream.writeln("%s: %s" % (flavour,self.getDescription(test)))
            doc = ""
            try:
                if hasattr(test, "test_name"):
                    doc = "./PYTHON.sh manage.py test --settings=settings-test " + test.test_name
            except:
                doc = test.__doc__ or ""
            doc = doc.strip()
            if doc:
                self.stream.writeln(Fore.MAGENTA + "DOC: " + Fore.GREEN + doc + Fore.RESET);
            self.stream.writeln(self.separator2)
            self.stream.writeln("%s" % err)


# class TestLoaderEx(object):
#     """
#     This class is responsible for loading tests according to various criteria
#     and returning them wrapped in a TestSuite
#     """
#     testMethodPrefix = 'test'
#     sortTestMethodsUsing = cmp
#     suiteClass = suite.TestSuite
#     _top_level_dir = None
#
#     def loadTestsFromTestCase(self, testCaseClass):
#         """Return a suite of all tests cases contained in testCaseClass"""
#         if issubclass(testCaseClass, suite.TestSuite):
#             raise TypeError("Test cases should not be derived from TestSuite." \
#                                 " Maybe you meant to derive from TestCase?")
#
#         # TestCase下面有很多个Test, 是如何处理的呢?
#         #
#         # class TestA(TestCase):
#         #    def test_a1(self):
#         #       pass
#         #    def test_a2(self):
#         #       pass
#         # 默认情况下TestA是未实例化的，而运行起来的TestCase是需要实例化的
#         # 但是map(TestA, testCaseNames) 之后就生成了 TestA的一个Test, 其中的testMethod被初始化
#         #
#         testCaseNames = self.getTestCaseNames(testCaseClass)
#
#         # 跳过
#         if not testCaseNames and hasattr(testCaseClass, 'runTest'):
#             testCaseNames = ['runTest']
#
#         #
#         loaded_suite = self.suiteClass(map(testCaseClass, testCaseNames))
#         return loaded_suite
#
#     def loadTestsFromModule(self, module, use_load_tests=True):
#         """Return a suite of all tests cases contained in the given module"""
#         tests = []
#         for name in dir(module):
#             # 例如: 遍历api.tests模块
#             obj = getattr(module, name)
#             # 遍历其中的type对象
#             if isinstance(obj, type) and issubclass(obj, case.TestCase):
#                 # 一个TestCase相关的东西变成一个TestSuit
#                 tests.append(self.loadTestsFromTestCase(obj))
#
#         # 其他的东西暂时不管了
#         load_tests = getattr(module, 'load_tests', None)
#         tests = self.suiteClass(tests)
#         if use_load_tests and load_tests is not None:
#             try:
#                 return load_tests(self, tests, None)
#             except Exception, e:
#                 return _make_failed_load_tests(module.__name__, e,
#                                                self.suiteClass)
#         return tests
#
#     def loadTestsFromName(self, name, module=None):
#         """Return a suite of all tests cases given a string specifier.
#
#         The name may resolve either to a module, a test case class, a
#         test method within a test case class, or a callable object which
#         returns a TestCase or TestSuite instance.
#
#         The method optionally resolves the names relative to a given module.
#         """
#         parts = name.split('.')
#         if module is None:
#             parts_copy = parts[:]
#             while parts_copy:
#                 try:
#                     module = __import__('.'.join(parts_copy))
#                     break
#                 except ImportError:
#                     del parts_copy[-1]
#                     if not parts_copy:
#                         raise
#             parts = parts[1:]
#         obj = module
#         for part in parts:
#             parent, obj = obj, getattr(obj, part)
#
#         if isinstance(obj, types.ModuleType):
#             return self.loadTestsFromModule(obj)
#         elif isinstance(obj, type) and issubclass(obj, case.TestCase):
#             return self.loadTestsFromTestCase(obj)
#         elif (isinstance(obj, types.UnboundMethodType) and
#               isinstance(parent, type) and
#               issubclass(parent, case.TestCase)):
#             name = parts[-1]
#             inst = parent(name)
#             return self.suiteClass([inst])
#         elif isinstance(obj, suite.TestSuite):
#             return obj
#         elif hasattr(obj, '__call__'):
#             test = obj()
#             if isinstance(test, suite.TestSuite):
#                 return test
#             elif isinstance(test, case.TestCase):
#                 return self.suiteClass([test])
#             else:
#                 raise TypeError("calling %s returned %s, not a test" %
#                                 (obj, test))
#         else:
#             raise TypeError("don't know how to make test from: %s" % obj)
#
#     def loadTestsFromNames(self, names, module=None):
#         """Return a suite of all tests cases found using the given sequence
#         of string specifiers. See 'loadTestsFromName()'.
#         """
#         suites = [self.loadTestsFromName(name, module) for name in names]
#         return self.suiteClass(suites)
#
#     def getTestCaseNames(self, testCaseClass):
#         """Return a sorted sequence of method names found within testCaseClass
#         """
#         def isTestMethod(attrname, testCaseClass=testCaseClass,
#                          prefix=self.testMethodPrefix):
#             # 有前缀
#             # 并且是函数，则为一个Test
#             return attrname.startswith(prefix) and \
#                 hasattr(getattr(testCaseClass, attrname), '__call__')
#
#         testFnNames = filter(isTestMethod, dir(testCaseClass))
#
#         # 将所有的 testFnNames 排序
#         if self.sortTestMethodsUsing:
#             testFnNames.sort(key=_CmpToKey(self.sortTestMethodsUsing))
#         return testFnNames
#
#     def discover(self, start_dir, pattern='test*.py', top_level_dir=None):
#         """Find and return all test modules from the specified start
#         directory, recursing into subdirectories to find them. Only test files
#         that match the pattern will be loaded. (Using shell style pattern
#         matching.)
#
#         All test modules must be importable from the top level of the project.
#         If the start directory is not the top level directory then the top
#         level directory must be specified separately.
#
#         If a test package name (directory with '__init__.py') matches the
#         pattern then the package will be checked for a 'load_tests' function. If
#         this exists then it will be called with loader, tests, pattern.
#
#         If load_tests exists then discovery does  *not* recurse into the package,
#         load_tests is responsible for loading all tests in the package.
#
#         The pattern is deliberately not stored as a loader attribute so that
#         packages can continue discovery themselves. top_level_dir is stored so
#         load_tests does not need to pass this argument in to loader.discover().
#         """
#         set_implicit_top = False
#         if top_level_dir is None and self._top_level_dir is not None:
#             # make top_level_dir optional if called from load_tests in a package
#             top_level_dir = self._top_level_dir
#         elif top_level_dir is None:
#             set_implicit_top = True
#             top_level_dir = start_dir
#
#         top_level_dir = os.path.abspath(top_level_dir)
#
#         if not top_level_dir in sys.path:
#             # all test modules must be importable from the top level directory
#             # should we *unconditionally* put the start directory in first
#             # in sys.path to minimise likelihood of conflicts between installed
#             # modules and development versions?
#             sys.path.insert(0, top_level_dir)
#         self._top_level_dir = top_level_dir
#
#         is_not_importable = False
#         if os.path.isdir(os.path.abspath(start_dir)):
#             start_dir = os.path.abspath(start_dir)
#             if start_dir != top_level_dir:
#                 is_not_importable = not os.path.isfile(os.path.join(start_dir, '__init__.py'))
#         else:
#             # support for discovery from dotted module names
#             try:
#                 __import__(start_dir)
#             except ImportError:
#                 is_not_importable = True
#             else:
#                 the_module = sys.modules[start_dir]
#                 top_part = start_dir.split('.')[0]
#                 start_dir = os.path.abspath(os.path.dirname((the_module.__file__)))
#                 if set_implicit_top:
#                     self._top_level_dir = self._get_directory_containing_module(top_part)
#                     sys.path.remove(top_level_dir)
#
#         if is_not_importable:
#             raise ImportError('Start directory is not importable: %r' % start_dir)
#
#         tests = list(self._find_tests(start_dir, pattern))
#         return self.suiteClass(tests)
#
#     def _get_directory_containing_module(self, module_name):
#         module = sys.modules[module_name]
#         full_path = os.path.abspath(module.__file__)
#
#         if os.path.basename(full_path).lower().startswith('__init__.py'):
#             return os.path.dirname(os.path.dirname(full_path))
#         else:
#             # here we have been given a module rather than a package - so
#             # all we can do is search the *same* directory the module is in
#             # should an exception be raised instead
#             return os.path.dirname(full_path)
#
#     def _get_name_from_path(self, path):
#         path = os.path.splitext(os.path.normpath(path))[0]
#
#         _relpath = os.path.relpath(path, self._top_level_dir)
#         assert not os.path.isabs(_relpath), "Path must be within the project"
#         assert not _relpath.startswith('..'), "Path must be within the project"
#
#         name = _relpath.replace(os.path.sep, '.')
#         return name
#
#     def _get_module_from_name(self, name):
#         __import__(name)
#         return sys.modules[name]
#
#     def _match_path(self, path, full_path, pattern):
#         # override this method to use alternative matching strategy
#         return fnmatch(path, pattern)
#
#     def _find_tests(self, start_dir, pattern):
#         """Used by discovery. Yields test suites it loads."""
#         paths = os.listdir(start_dir)
#
#         for path in paths:
#             full_path = os.path.join(start_dir, path)
#             if os.path.isfile(full_path):
#                 if not VALID_MODULE_NAME.match(path):
#                     # valid Python identifiers only
#                     continue
#                 if not self._match_path(path, full_path, pattern):
#                     continue
#                 # if the test file matches, load it
#                 name = self._get_name_from_path(full_path)
#                 try:
#                     module = self._get_module_from_name(name)
#                 except:
#                     yield _make_failed_import_test(name, self.suiteClass)
#                 else:
#                     mod_file = os.path.abspath(getattr(module, '__file__', full_path))
#                     realpath = os.path.splitext(os.path.realpath(mod_file))[0]
#                     fullpath_noext = os.path.splitext(os.path.realpath(full_path))[0]
#                     if realpath.lower() != fullpath_noext.lower():
#                         module_dir = os.path.dirname(realpath)
#                         mod_name = os.path.splitext(os.path.basename(full_path))[0]
#                         expected_dir = os.path.dirname(full_path)
#                         msg = ("%r module incorrectly imported from %r. Expected %r. "
#                                "Is this module globally installed?")
#                         raise ImportError(msg % (mod_name, module_dir, expected_dir))
#                     yield self.loadTestsFromModule(module)
#             elif os.path.isdir(full_path):
#                 if not os.path.isfile(os.path.join(full_path, '__init__.py')):
#                     continue
#
#                 load_tests = None
#                 tests = None
#                 if fnmatch(path, pattern):
#                     # only check load_tests if the package directory itself matches the filter
#                     name = self._get_name_from_path(full_path)
#                     package = self._get_module_from_name(name)
#                     load_tests = getattr(package, 'load_tests', None)
#                     tests = self.loadTestsFromModule(package, use_load_tests=False)
#
#                 if load_tests is None:
#                     if tests is not None:
#                         # tests loaded from package file
#                         yield tests
#                     # recurse into the package
#                     for test in self._find_tests(full_path, pattern):
#                         yield test
#                 else:
#                     try:
#                         yield load_tests(self, tests, pattern)
#                     except Exception, e:
#                         yield _make_failed_load_tests(package.__name__, e,
#                                                       self.suiteClass)

