import unittest
import re
try:
    from unittest import mock
except:
    import mock

from flow.command_runner.executors import lsf
from flow.command_runner.resource import ResourceException
from pythonlsf import lsf as lsf_driver

def _create_expected_limits():
    return [lsf_driver.DEFAULT_RLIMIT] * lsf_driver.LSF_RLIM_NLIMITS


class MakeRusageTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual("", lsf._make_rusage_string(require={}, reserve={}))

    def test_select(self):
        require = {"memory": 150, "temp_space": 3, "min_proc": 4}
        reserve = {}

        rsrc = lsf._make_rusage_string(require=require, reserve=reserve)
        select = re.match("^select\[([^]]*)\]$", rsrc)
        self.assertTrue(select)
        items = sorted(select.group(1).split(" && "))
        self.assertEqual(["gtmp>=3", "mem>=150", "ncpus>=4"], items)

    def test_implied_select(self):
        require = {}
        reserve = {"memory": 150, "temp_space": 3}

        rsrc = lsf._make_rusage_string(require=require, reserve=reserve)
        select = re.search("select\[([^]]*)\]", rsrc)
        self.assertTrue(select)
        items = sorted(select.group(1).split(" && "))
        self.assertEqual(["gtmp>=3", "mem>=150"], items)

        rusage = re.search("rusage\[([^]]*)\]", rsrc)
        self.assertTrue(rusage)
        items = sorted(rusage.group(1).split(":"))
        self.assertEqual(["gtmp=3", "mem=150"], items)

    def test_reserve_non_reservable(self):
        require = {}
        reserve = {"min_proc": 4}
        self.assertRaises(ResourceException, lsf._make_rusage_string,
                require=require, reserve=reserve)


class GetRlimitsTest(unittest.TestCase):
    AVAILABLE_RLIMITS = [
            #('max_resident_memory', lsf_driver.LSF_RLIMIT_RSS),
            ('max_virtual_memory', lsf_driver.LSF_RLIMIT_VMEM),
            ('max_processes', lsf_driver.LSF_RLIMIT_PROCESS),
            ('max_threads', lsf_driver.LSF_RLIMIT_THREAD),
            ('max_open_files', lsf_driver.LSF_RLIMIT_NOFILE),
            ('max_stack_size', lsf_driver.LSF_RLIMIT_STACK)
    ]

    def simple_rlim_success(self, name, index, value=42):
        kwargs = {name: value}
        expected_limits = _create_expected_limits()
        expected_limits[index] = value
        limits = lsf.get_rlimits(**kwargs)
        self.assertEqual(limits, expected_limits)

    def simple_rlim_failure(self, name):
        kwargs = {name: mock.Mock()}
        self.assertRaises(TypeError, lsf.get_rlimits, **kwargs)


    def test_defaults(self):
        expected_limits = _create_expected_limits()
        limits = lsf.get_rlimits()
        self.assertEqual(limits, expected_limits)


    def test_all_success(self):
        for name, index in self.AVAILABLE_RLIMITS:
            self.simple_rlim_success(name, index)

    def test_all_failure(self):
        for name, index in self.AVAILABLE_RLIMITS:
            self.simple_rlim_failure(name)


class CreateRequestTest(unittest.TestCase):
    def setUp(self):
        self.default_queue = 'serious queue'
        self.dispatcher = lsf.LSFExecutor(default_queue=self.default_queue)

        self.bad_type = mock.Mock()
        self.bad_type.__str__ = lambda x: None


    def test_name_success(self):
        name = 'different name'
        request = self.dispatcher.create_request(name=name)
        self.assertEqual(request.jobName, name)
        self.assertEqual(request.options,
                lsf_driver.SUB_JOB_NAME + lsf_driver.SUB_QUEUE)

    def test_name_failure(self):
        self.assertRaises(TypeError,
                self.dispatcher.create_request, name=self.bad_type)

    def test_mail_user_success(self):
        mail_user = 'someone@some.whe.re'
        request = self.dispatcher.create_request(mail_user=mail_user)
        self.assertEqual(request.mailUser, mail_user)
        self.assertEqual(request.options,
                lsf_driver.SUB_MAIL_USER + lsf_driver.SUB_QUEUE)

    def test_mail_user_failure(self):
        self.assertRaises(TypeError,
                self.dispatcher.create_request, mail_user=self.bad_type)


    def test_queue_success(self):
        queue = 'different queue'
        request = self.dispatcher.create_request(queue=queue)
        self.assertEqual(request.queue, queue)
        self.assertEqual(request.options, lsf_driver.SUB_QUEUE)

    def test_queue_failure(self):
        self.assertRaises(TypeError,
                self.dispatcher.create_request, queue=self.bad_type)


    def test_stdout_success(self):
        stdout = '/tmp/stdout/path'
        request = self.dispatcher.create_request(stdout=stdout)
        self.assertEqual(request.queue, self.default_queue)
        self.assertEqual(request.outFile, stdout)
        self.assertEqual(request.options,
                lsf_driver.SUB_QUEUE + lsf_driver.SUB_OUT_FILE)

    def test_stdout_failure(self):
        self.assertRaises(TypeError,
                self.dispatcher.create_request, stdout=self.bad_type)


    def test_stderr_success(self):
        stderr = '/tmp/stderr/path'
        request = self.dispatcher.create_request(stderr=stderr)
        self.assertEqual(request.queue, self.default_queue)
        self.assertEqual(request.errFile, stderr)
        self.assertEqual(request.options,
                lsf_driver.SUB_QUEUE + lsf_driver.SUB_ERR_FILE)

    def test_stderr_failure(self):
        self.assertRaises(TypeError,
                self.dispatcher.create_request, stderr=self.bad_type)

    def test_resources(self):
        value = 4000
        limit = {"max_virtual_memory": value}
        reserve = {"memory": 4096, "temp_space": 10}
        require = {"min_proc": 8}

        resources = {"limit": limit, "reserve": reserve, "require": require}
        request = self.dispatcher.create_request(resources=resources)
        expected_limits = _create_expected_limits()
        expected_limits[lsf_driver.LSF_RLIMIT_VMEM] = value
        self.assertEqual(request.queue, self.default_queue)

        for i, x in enumerate(expected_limits):
            self.assertEqual(request.rLimits[i], x)

        self.assertTrue(request.options | lsf_driver.SUB_RES_REQ)
        select = re.search("select\[([^]]*)]", request.resReq)
        rusage = re.search("rusage\[([^]]*)]", request.resReq)
        self.assertTrue(select)
        self.assertTrue(rusage)

        sitems = sorted(select.group(1).split(" && "))
        ritems = sorted(rusage.group(1).split(":"))

        self.assertEqual(["gtmp>=10", "mem>=4096", "ncpus>=8"], sitems)
        self.assertEqual(["gtmp=10", "mem=4096"], ritems)

    def test_post_exec_cmd(self):
        post_exec_cmd = None
        request = self.dispatcher.create_request(post_exec_cmd=post_exec_cmd)

        self.assertEqual(request.options3, 0)
        self.assertEqual(request.postExecCmd, None)

        post_exec_cmd = 'echo "something"'
        request = self.dispatcher.create_request(post_exec_cmd=post_exec_cmd)

        self.assertEqual(request.options3, lsf_driver.SUB3_POST_EXEC)
        self.assertEqual(request.postExecCmd, post_exec_cmd)


if '__main__' == __name__:
    unittest.main()
