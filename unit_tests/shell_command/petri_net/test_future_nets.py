from flow.shell_command.petri_net import actions
from flow.shell_command.petri_net import future_nets

import mock
import unittest


class FakeShellCommandNet(future_nets.ShellCommandNet):
    def __init__(self, *args, **kwargs):
        self.DISPATCH_ACTION = mock.Mock()
        future_nets.ShellCommandNet.__init__(self, *args, **kwargs)


class ShellCommandNetTest(unittest.TestCase):
    def setUp(self):
        self.arg1 = mock.Mock()
        self.arg2 = mock.Mock()
        self.net = FakeShellCommandNet(name='foo',
                arg1=self.arg1, arg2=self.arg2)

    def test_unreachable_places(self):
        unreachable_places = {p for p in self.net.places if not p.arcs_in}

        expected_unreachable_places = {
            self.net.start,
            self.net.dispatch_failure_place,
            self.net.dispatch_success_place,
            self.net.execute_begin_place,
            self.net.execute_failure_place,
            self.net.execute_success_place,
        }
        self.assertItemsEqual(expected_unreachable_places, unreachable_places)

    def test_dead_end_places(self):
        dead_end_places = {p for p in self.net.places if not p.arcs_out}

        expected_dead_end_places = {
            self.net.success,
            self.net.failure,
        }
        self.assertItemsEqual(expected_dead_end_places, dead_end_places)


    def test_action_set(self):
        self.assertEqual(self.net.DISPATCH_ACTION,
                self.net.dispatch.action.cls)
        expected_args = {
            'arg1': self.arg1,
            'arg2': self.arg2,
            "msg: dispatch_success": self.net.dispatch_success_place,
            "msg: dispatch_failure": self.net.dispatch_failure_place,
            "msg: execute_begin": self.net.execute_begin_place,
            "msg: execute_success": self.net.execute_success_place,
            "msg: execute_failure": self.net.execute_failure_place,
        }

        self.assertItemsEqual(expected_args,
                self.net.dispatch.action.args)


    def test_path_to_success(self):
        self.assertIn(self.net.dispatch, self.net.start.arcs_out)
        self.assertIn(self.net.dispatching, self.net.dispatch.arcs_out)
        self.assertIn(self.net.dispatch_success, self.net.dispatching.arcs_out)
        self.assertIn(self.net.pending, self.net.dispatch_success.arcs_out)
        self.assertIn(self.net.execute_begin, self.net.pending.arcs_out)
        self.assertIn(self.net.running, self.net.execute_begin.arcs_out)
        self.assertIn(self.net.execute_success, self.net.running.arcs_out)
        self.assertIn(self.net.success, self.net.execute_success.arcs_out)

    def test_path_to_failure_from_dispatch(self):
        self.assertIn(self.net.dispatch, self.net.start.arcs_out)
        self.assertIn(self.net.dispatching, self.net.dispatch.arcs_out)
        self.assertIn(self.net.dispatch_failure, self.net.dispatching.arcs_out)
        self.assertIn(self.net.failure, self.net.dispatch_failure.arcs_out)

    def test_path_to_failure_from_execute(self):
        self.assertIn(self.net.dispatch, self.net.start.arcs_out)
        self.assertIn(self.net.dispatching, self.net.dispatch.arcs_out)
        self.assertIn(self.net.dispatch_success, self.net.dispatching.arcs_out)
        self.assertIn(self.net.pending, self.net.dispatch_success.arcs_out)
        self.assertIn(self.net.execute_begin, self.net.pending.arcs_out)
        self.assertIn(self.net.running, self.net.execute_begin.arcs_out)
        self.assertIn(self.net.execute_failure, self.net.running.arcs_out)
        self.assertIn(self.net.failure, self.net.execute_failure.arcs_out)


    def test_lsf_net(self):
        self.assertEqual(actions.LSFDispatchAction,
                future_nets.LSFCommandNet.DISPATCH_ACTION)

    def test_fork_net(self):
        self.assertEqual(actions.ForkDispatchAction,
                future_nets.ForkCommandNet.DISPATCH_ACTION)


if __name__ == "__main__":
    unittest.main()
