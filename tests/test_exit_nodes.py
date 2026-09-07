import unittest
from unittest.mock import Mock, patch

import tailwrap


class ExitNodeMenuTests(unittest.TestCase):
    def setUp(self):
        self.indicator = object()
        self.data = {
            "Peer": {
                "nodekey:a": {"ID": "stable-a", "HostName": "A",
                              "TailscaleIPs": ["100.64.0.1"], "ExitNodeOption": True},
                "nodekey:b": {"ID": "stable-b", "HostName": "B",
                              "TailscaleIPs": ["100.64.0.2"], "ExitNodeOption": True},
            }
        }

    def choices(self):
        self.menu = tailwrap.build_exit_nodes_menu(self.data, self.indicator)
        self.addCleanup(self.menu.destroy)
        return [item for item in self.menu.get_children()
                if isinstance(item, tailwrap.Gtk.RadioMenuItem)]

    def test_build_restores_stable_id_without_commands(self):
        self.data["ExitNodeStatus"] = {"ID": "stable-b"}
        with patch.object(tailwrap, "set_exit_node") as change:
            choices = self.choices()
            self.assertEqual([item.get_active() for item in choices], [False, False, True])
            change.assert_not_called()

    def test_switch_and_disable_send_one_command_each(self):
        with patch.object(tailwrap, "set_exit_node") as change:
            choices = self.choices()
            change.assert_not_called()
            for index, ip in [(1, "100.64.0.1"), (2, "100.64.0.2"), (0, None)]:
                change.reset_mock()
                choices[index].activate()
                change.assert_called_once_with(ip, self.indicator)

    def test_null_exit_status(self):
        self.data["ExitNodeStatus"] = None
        with patch.object(tailwrap, "set_exit_node") as change:
            self.assertTrue(self.choices()[0].get_active())
            change.assert_not_called()

    def test_exit_command_and_async_indicator(self):
        for ip in ["100.64.0.1", None]:
            with self.subTest(ip=ip), patch.object(tailwrap, "run_tailscale") as run, \
                    patch.object(tailwrap.GLib, "idle_add") as idle:
                tailwrap.set_exit_node(ip, self.indicator)
                args, callback, user_data = run.call_args.args
                self.assertEqual(args, ["tailscale", "set", f"--exit-node={ip or ''}"])
                callback(Mock(), object(), user_data)
                idle.assert_called_once_with(tailwrap.update_menu, self.indicator)

    def test_preference_command_and_async_indicator(self):
        with patch.object(tailwrap, "run_tailscale") as run, \
                patch.object(tailwrap.GLib, "idle_add") as idle:
            tailwrap.toggle_pref("accept-routes", True, self.indicator)
            args, callback, user_data = run.call_args.args
            self.assertEqual(args, ["tailscale", "set", "--accept-routes=true"])
            callback(Mock(), object(), user_data)
            idle.assert_called_once_with(tailwrap.update_menu, self.indicator)


if __name__ == "__main__":
    unittest.main()
