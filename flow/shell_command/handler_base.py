from flow.configuration.settings.injector import setting
from flow.handler import Handler
from flow.shell_command.messages import ShellCommandSubmitMessage
from flow.util import environment as env_util
from injector import inject
from twisted.internet import defer, reactor
from flow.shell_command.monitor import ExecutorMonitor

import logging
import os
import sys
import twisted.python.procutils


LOG = logging.getLogger(__name__)


@inject(default_environment=setting('shell_command.default_environment', {}),
        mandatory_environment=setting(
            'shell_command.mandatory_environment', {}))
class ShellCommandSubmitMessageHandler(Handler):
    message_class = ShellCommandSubmitMessage

    @property
    def executable(self):
        if is_executable(os.path.abspath(self.executable_name)):
            return os.path.abspath(self.executable_name)
        elif is_executable(os.path.join(os.path.dirname(sys.executable),
                self.executable_name)):
            return os.path.join(os.path.dirname(sys.executable),
                    self.executable_name)
        else:
            return twisted.python.procutils.which(self.executable_name)[0]

    def assemble_environment(self, message):
        return env_util.merge_and_sanitize_environments(
                self.default_environment,
                message.get('environment', {}),
                self.mandatory_environment)

    def _get_value_if_root(self, value, requested_uid, field_name):
        actual_uid = os.getuid()
        if actual_uid == 0:
            return value
        elif actual_uid == requested_uid:
            return None
        else:
            raise RuntimeError(
                    'Could not set %s to %s (current uid %s, message uid = %s)'
                    % (field_name, value, actual_uid, requested_uid))


    def uid(self, message):
        return self._get_value_if_root(message.user_id, message.user_id, 'uid')

    def gid(self, message):
        return self._get_value_if_root(message.group_id, message.user_id, 'gid')


    def _handle_message(self, message):
        monitor = ExecutorMonitor(message.get('executor_data', {}),
                log_file=message.get('executor_data', {}).get('stderr'),
                uid=self.uid(message), gid=self.gid(message))

        reactor.spawnProcess(monitor,
                self.executable, [self.executable, '--job_id_fd', '3'],
                env=self.assemble_environment(message),
                uid=self.uid(message), gid=self.gid(message),
                path=message.get('working_directory', '/tmp'),
                childFDs={0: 'w', 1: 'r', 2: 'r', 3: 'r'})

        return self.add_monitor_callbacks(message.get('callback_data', {}),
                monitor)

    def add_monitor_callbacks(self, callback_data, monitor):
        job_id_handled = defer.Deferred()
        job_ended_handled = defer.Deferred()

        monitor.job_id_deferred.addCallbacks(self.on_job_id_success,
                self.on_job_id_failure,
                callbackKeywords={'callback_data': callback_data,
                    'job_id_handled': job_id_handled},
                errbackKeywords={'callback_data': callback_data,
                    'job_id_handled': job_id_handled})
        monitor.job_ended_deferred.addCallbacks(self.on_job_ended_success,
                self.on_job_ended_failure,
                callbackKeywords={'callback_data': callback_data,
                    'job_ended_handled': job_ended_handled},
                errbackKeywords={'callback_data': callback_data,
                    'job_ended_handled': job_ended_handled})

        return defer.gatherResults([job_id_handled, job_ended_handled],
                consumeErrors=True)

    def send_message(self, place_name, callback_data, token_data=None):
        net_key = callback_data['net_key']
        color = callback_data['color']
        color_group_idx = callback_data['color_group_idx']
        place_idx = callback_data[place_name]

        return self.service_interfaces['orchestrator'].create_token(
                net_key=net_key, place_idx=place_idx, color=color,
                color_group_idx=color_group_idx, data=token_data)


def is_executable(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
