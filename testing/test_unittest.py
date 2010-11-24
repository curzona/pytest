import pytest

def test_simple_unittest(testdir):
    testpath = testdir.makepyfile("""
        import unittest
        pytest_plugins = "pytest_unittest"
        class MyTestCase(unittest.TestCase):
            def testpassing(self):
                self.assertEquals('foo', 'foo')
            def test_failing(self):
                self.assertEquals('foo', 'bar')
    """)
    reprec = testdir.inline_run(testpath)
    assert reprec.matchreport("testpassing").passed
    assert reprec.matchreport("test_failing").failed

def test_isclasscheck_issue53(testdir):
    testpath = testdir.makepyfile("""
        import unittest
        class _E(object):
            def __getattr__(self, tag):
                pass
        E = _E()
    """)
    result = testdir.runpytest(testpath)
    assert result.ret == 0

def test_setup(testdir):
    testpath = testdir.makepyfile(test_two="""
        import unittest
        class MyTestCase(unittest.TestCase):
            def setUp(self):
                self.foo = 1
            def test_setUp(self):
                self.assertEquals(1, self.foo)
    """)
    reprec = testdir.inline_run(testpath)
    rep = reprec.matchreport("test_setUp")
    assert rep.passed

def test_new_instances(testdir):
    testpath = testdir.makepyfile("""
        import unittest
        class MyTestCase(unittest.TestCase):
            def test_func1(self):
                self.x = 2
            def test_func2(self):
                assert not hasattr(self, 'x')
    """)
    reprec = testdir.inline_run(testpath)
    reprec.assertoutcome(passed=2)

def test_teardown(testdir):
    testpath = testdir.makepyfile("""
        import unittest
        pytest_plugins = "pytest_unittest" # XXX
        class MyTestCase(unittest.TestCase):
            l = []
            def test_one(self):
                pass
            def tearDown(self):
                self.l.append(None)
        class Second(unittest.TestCase):
            def test_check(self):
                self.assertEquals(MyTestCase.l, [None])
    """)
    reprec = testdir.inline_run(testpath)
    passed, skipped, failed = reprec.countoutcomes()
    assert failed == 0, failed
    assert passed == 2
    assert passed + skipped + failed == 2

def test_module_level_pytestmark(testdir):
    testpath = testdir.makepyfile("""
        import unittest
        import pytest
        pytestmark = pytest.mark.xfail
        class MyTestCase(unittest.TestCase):
            def test_func1(self):
                assert 0
    """)
    reprec = testdir.inline_run(testpath, "-s")
    reprec.assertoutcome(skipped=1)

def test_setup_setUpClass(testdir):
    testpath = testdir.makepyfile("""
        import unittest
        import pytest
        class MyTestCase(unittest.TestCase):
            x = 0
            @classmethod
            def setUpClass(cls):
                cls.x += 1
            def test_func1(self):
                assert self.x == 1
            def test_func2(self):
                assert self.x == 1
            @classmethod
            def tearDownClass(cls):
                cls.x -= 1
        def test_teareddown():
            assert MyTestCase.x == 0
    """)
    reprec = testdir.inline_run(testpath)
    reprec.assertoutcome(passed=3)

def test_setup_class(testdir):
    testpath = testdir.makepyfile("""
        import unittest
        import pytest
        class MyTestCase(unittest.TestCase):
            x = 0
            def setup_class(cls):
                cls.x += 1
            def test_func1(self):
                assert self.x == 1
            def test_func2(self):
                assert self.x == 1
            def teardown_class(cls):
                cls.x -= 1
        def test_teareddown():
            assert MyTestCase.x == 0
    """)
    reprec = testdir.inline_run(testpath)
    reprec.assertoutcome(passed=3)


@pytest.mark.multi(type=['Error', 'Failure'])
def test_testcase_adderrorandfailure_defers(testdir, type):
    testdir.makepyfile("""
        from unittest import TestCase
        import pytest
        class MyTestCase(TestCase):
            def run(self, result):
                excinfo = pytest.raises(ZeroDivisionError, lambda: 0/0)
                try:
                    result.add%s(self, excinfo._excinfo)
                except KeyboardInterrupt:
                    raise
                except:
                    pytest.fail("add%s should not raise")
            def test_hello(self):
                pass
    """ % (type, type))
    result = testdir.runpytest()
    assert 'should not raise' not in result.stdout.str()

@pytest.mark.multi(type=['Error', 'Failure'])
def test_testcase_custom_exception_info(testdir, type):
    testdir.makepyfile("""
        from unittest import TestCase
        import py, pytest
        class MyTestCase(TestCase):
            def run(self, result):
                excinfo = pytest.raises(ZeroDivisionError, lambda: 0/0)
                # we fake an incompatible exception info
                from _pytest.monkeypatch import monkeypatch
                mp = monkeypatch()
                def t(*args):
                    mp.undo()
                    raise TypeError()
                mp.setattr(py.code, 'ExceptionInfo', t)
                try:
                    excinfo = excinfo._excinfo
                    result.add%(type)s(self, excinfo)
                finally:
                    mp.undo()
            def test_hello(self):
                pass
    """ % locals())
    result = testdir.runpytest()
    result.stdout.fnmatch_lines([
        "NOTE: Incompatible Exception Representation*",
        "*ZeroDivisionError*",
        "*1 failed*",
    ])

def test_testcase_totally_incompatible_exception_info(testdir):
    item, = testdir.getitems("""
        from unittest import TestCase
        class MyTestCase(TestCase):
            def test_hello(self):
                pass
    """)
    item.addError(None, 42)
    excinfo = item._excinfo
    assert 'ERROR: Unknown Incompatible' in str(excinfo.getrepr())



class TestTrialUnittest:
    def setup_class(cls):
        pytest.importorskip("twisted.trial.unittest")

    def test_trial_exceptions_with_skips(self, testdir):
        testdir.makepyfile("""
            from twisted.trial import unittest
            import pytest
            class TC(unittest.TestCase):
                def test_hello(self):
                    pytest.skip("skip_in_method")
                @pytest.mark.skipif("sys.version_info != 1")
                def test_hello2(self):
                    pass
                @pytest.mark.xfail(reason="iwanto")
                def test_hello3(self):
                    assert 0
                def test_hello4(self):
                    pytest.xfail("i2wanto")

            class TC2(unittest.TestCase):
                def setup_class(cls):
                    pytest.skip("skip_in_setup_class")
                def test_method(self):
                    pass
        """)
        result = testdir.runpytest("-rxs")
        assert result.ret == 0
        result.stdout.fnmatch_lines_random([
            "*skip_in_setup_class*",
            "*iwanto*",
            "*i2wanto*",
            "*sys.version_info*",
            "*skip_in_method*",
            "*3 skipped*2 xfail*",
        ])

    def test_trial_error(self, testdir):
        testdir.makepyfile("""
            from twisted.trial.unittest import TestCase
            from twisted.internet.defer import inlineCallbacks
            from twisted.internet import reactor

            class TC(TestCase):
                def test_one(self):
                    crash

                def test_two(self):
                    def f(_):
                        crash
                    
                    return reactor.callLater(0.3, f)

                def test_three(self):
                    def f():
                        pass # will never get called
                    return reactor.callLater(0.3, f)
                # will crash at teardown

                def test_four(self):
                    def f(_):
                        reactor.callLater(0.3, f)
                        crash

                    return reactor.callLater(0.3, f)
                # will crash both at test time and at teardown
        """)
        result = testdir.runpytest()

    def test_trial_pdb(self, testdir):
        p = testdir.makepyfile("""
            from twisted.trial import unittest
            import pytest
            class TC(unittest.TestCase):
                def test_hello(self):
                    assert 0, "hellopdb"
        """)
        child = testdir.spawn_pytest(p)
        child.expect("hellopdb")
        child.sendeof()

def test_djangolike_testcase(testdir):
    # contributed from Morten Breekevold
    testdir.makepyfile("""
        from unittest import TestCase, main

        class DjangoLikeTestCase(TestCase):

            def setUp(self):
                print ("setUp()")

            def test_presetup_has_been_run(self):
                print ("test_thing()")
                self.assertTrue(hasattr(self, 'was_presetup'))

            def tearDown(self):
                print ("tearDown()")

            def __call__(self, result=None):
                try:
                    self._pre_setup()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    import sys
                    result.addError(self, sys.exc_info())
                    return
                super(DjangoLikeTestCase, self).__call__(result)
                try:
                    self._post_teardown()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception:
                    import sys
                    result.addError(self, sys.exc_info())
                    return

            def _pre_setup(self):
                print ("_pre_setup()")
                self.was_presetup = True

            def _post_teardown(self):
                print ("_post_teardown()")
    """)
    result = testdir.runpytest("-s")
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        "*_pre_setup()*",
        "*setUp()*",
        "*test_thing()*",
        "*tearDown()*",
        "*_post_teardown()*",
    ])