from flow.petri_net.actions.merge import BasicMergeAction
from flow.petri_net.net import Net, ColorGroup, Token
from flow.petri_net.net import PlaceNotFoundError, ForeignTokenError
from flow.petri_net.transitions.basic import BasicTransition
import flow.redisom as rom

from test_helpers import NetTest
from unittest import main
from mock import MagicMock, Mock, ANY

class TestNet(NetTest):
    def setUp(self):
        NetTest.setUp(self)
        self.token = self.create_simple_token()

    def create_simple_token(self, data=None):
        color_group = self.net.add_color_group(size=1)
        return self.net.create_token(color_group.begin, color_group.idx, data)

    def test_put_token_place_not_found(self):
        token_idx = self.token.index.value

        self.assertRaises(PlaceNotFoundError, self.net.put_token, 0,
                self.token)

    def test_put_foreign_token(self):
        othernet = Net.create(self.conn, "net2")
        place = othernet.add_place("home")
        self.assertRaises(ForeignTokenError, othernet.put_token, 0,
                self.token)

    def test_put_token(self):
        start = self.net.add_place("start")

        self.assertEqual(0, len(self.net.color_marking))
        self.assertEqual(0, len(self.net.group_marking))

        token_idx = self.token.index.value
        color = self.token.color.value
        color_group_idx = self.token.color_group_idx.value

        place_idx = 0
        color_key = self.net.marking_key(color, place_idx)
        group_key = self.net.marking_key(color_group_idx, place_idx)

        rv = self.net.put_token(place_idx, self.token)

        self.assertEqual(0, rv)
        expected_color_marking = {color_key: token_idx}
        self.assertEqual(expected_color_marking, self.net.color_marking.value)
        self.assertEqual({group_key: 1}, self.net.group_marking.value)

        # make sure putting the same token is idempotent
        rv = self.net.put_token(place_idx, self.token)
        self.assertEqual(0, rv)
        self.assertEqual(expected_color_marking, self.net.color_marking.value)
        self.assertEqual({group_key: 1}, self.net.group_marking.value)

        # make sure putting a new token is an error
        new_token = self.net.create_token(color=color,
                color_group_idx=color_group_idx)

        rv = self.net.put_token(place_idx, new_token)
        self.assertEqual(-1, rv)
        self.assertEqual(expected_color_marking, self.net.color_marking.value)
        self.assertEqual({group_key: 1}, self.net.group_marking.value)

    def test_notify_place_no_token(self):
        home = self.net.add_place("home")
        place_idx = home.index.value

        svcs = MagicMock()
        color = 0
        self.net.notify_place(place_idx, color, svcs)

        self.assertEqual(0, len(svcs.mock_calls))
        self.assertRaises(rom.NotInRedisError, getattr,
                home.first_token_timestamp, "value")

    def test_notify_place_wrong_color(self):
        home = self.net.add_place("home")
        place_idx = home.index.value

        self.net.put_token(place_idx, self.token)
        color = self.token.color.value

        svcs = MagicMock()
        self.net.notify_place(place_idx, color+1, svcs)

        self.assertEqual(0, len(svcs.mock_calls))
        self.assertRaises(rom.NotInRedisError, getattr,
                home.first_token_timestamp, "value")

    def test_notify_place(self):
        home = self.net.add_place("home")
        place_idx = home.index.value
        home.arcs_out = [0, 1, 2]

        self.net.put_token(place_idx, self.token)
        color = self.token.color.value

        orchestrator = Mock()
        svcs = {"orchestrator": orchestrator}
        self.conn.time = lambda: (123, 0)
        self.net.notify_place(place_idx, color, svcs)

        calls = orchestrator.method_calls
        self.assertEqual(3, len(calls))

        fn = orchestrator.notify_transition
        fn.assert_any_call(net_key='net', transition_idx=0,
                place_idx=place_idx, token_idx=ANY)
        fn.assert_any_call(net_key='net', transition_idx=1,
                place_idx=place_idx, token_idx=ANY)
        fn.assert_any_call(net_key='net', transition_idx=2,
                place_idx=place_idx, token_idx=ANY)
        self.assertEqual(123.0, home.first_token_timestamp.value)


    def test_delete(self):
        p = self.net.add_place('p')
        trans = self.net.add_transition(BasicTransition)
        a = BasicMergeAction.create(self.conn, key=trans.action_key)
        cg = self.net.add_color_group(3)
        tok = self.net.create_token(cg.begin, cg.idx)

        self.net.delete()
        print list(self.net.associated_iterkeys_for_attribute('place'))
        print [i for i in self.net.associated_iterkeys()]

        self.assertEqual([], self.conn.keys())


if __name__ == "__main__":
    main()
