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
                    for subsuite in item:
                        test_case_class = subsuite.__class__.__name__
                        break
                    app_path = ".".join(app_module.__name__.split('.')[:-1])
                    add_full_test_name_2_testsuit(item, app_path + "." + test_case_class)
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
        # 除了TestSuit和TestCase还可能有什么呢?
        if isinstance(t, unittest.TestSuite):
            count += traverse_test_suit(t)
        elif isinstance(t, unittest.TestCase):
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
    if isinstance(suit, unittest.TestSuite):
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
        CYTextTestResult.test_case_total_count = total_count
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

import time

class CYTextTestResult(unittest.TextTestResult):
    test_case_total_count = 0
    no_slow_test = False

    def __init__(self, stream, descriptions, verbosity):
        super(CYTextTestResult, self).__init__(stream, descriptions, verbosity)
        self.test_case_start_time = 0
        self.test_start_time = 0
        self.slows = []

    def startTest(self, test):
        super(CYTextTestResult, self).startTest(test)

        global test_case_start_time

        if self.testsRun == 1:
            test_case_start_time = time.time()

        self.test_start_time = time.time()

        print (Fore.GREEN + "[%04d/%04d %4.1f%% T: %6.2fs]" % (self.testsRun, self.test_case_total_count,
                                                               self.testsRun * 100 / max(1, self.test_case_total_count),
                                                               time.time() - test_case_start_time) +
               Fore.RESET + " : " + Fore.RED + str(test) + Fore.RESET)


    def stopTest(self, test):
        super(CYTextTestResult, self).stopTest(test)
        elasped = time.time() - self.test_start_time

        if elasped > 0.2:
            self.slows.append((elasped, str(test)))

    def printErrorList(self, flavour, errors):
        """
            最后汇总，输出测试的结果:
        """
        if not self.no_slow_test and self.slows:
            self.slows.sort(reverse=True)
            self.stream.writeln(Fore.MAGENTA + "------------------------------------------------------------------" + Fore.RESET)
            index = 0
            # 一次展示10个
            for elapsed, test in self.slows[:10]:
                index += 1
                self.stream.writeln("SLOW-[%02d]: T: %.3fs --> %s" % (index, elapsed, test))
                if index % 10 == 0:
                    self.stream.writeln(Fore.GREEN + "------------------------------------------------------------------" + Fore.RESET)
            self.stream.writeln(Fore.MAGENTA + "------------------------------------------------------------------" + Fore.RESET)
            self.slows = []

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

