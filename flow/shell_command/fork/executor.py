from flow import exit_codes
from flow.shell_command import util
from flow.shell_command.executor_base import ExecutorBase, send_message
from twisted.internet import defer

import flow.interfaces
import logging
import os
import socket
import subprocess


LOG = logging.getLogger(__name__)


class ForkExecutor(ExecutorBase):
    def on_job_id(self, job_id, callback_data, service_interfaces):
        deferreds = []
        dispatch_data = {'job_id': job_id}
        deferreds.append(send_message(
            'msg: dispatch_success', callback_data, service_interfaces,
            token_data=dispatch_data))

        execute_data = {'hostname': socket.gethostname()}
        deferreds.append(send_message(
            'msg: execute_begin', callback_data, service_interfaces,
            token_data=execute_data))

        return defer.gatherResults(deferreds, consumeErrors=True)

    def on_failure(self, exit_code, callback_data, service_interfaces):
        return send_message('msg: execute_failure',
                callback_data, service_interfaces)

    def on_success(self, callback_data, service_interfaces):
        return send_message('msg: execute_success',
                callback_data, service_interfaces)


    def execute_command_line(self, job_id_callback, command_line,
            executor_data, resources):
        stderr = executor_data.get('stderr')
        stdin = executor_data.get('stdin')
        stdout = executor_data.get('stdout')

        stderr_fh = None
        stdin_fh = None
        stdout_fh = None
        try:
            if stderr:
                stderr_fh = open(stderr, 'a')
            if stdin:
                stdin_fh = open(stdin, 'r')
            if stdout:
                stdout_fh = open(stdout, 'a')

            LOG.debug('executing command %s', " ".join(command_line))
            p = subprocess.Popen(command_line, close_fds=True,
                    stderr=stderr_fh, stdin=stdin_fh, stdout=stdout_fh)
            job_id_callback(p.pid)

            returncode = p.wait()

            if returncode < 0:
                exit_code = exit_codes.EXECUTE_ERROR
            else:
                exit_code = returncode

        except OSError:
            LOG.exception('Executor got OSError')
            raise
        finally:
            if stderr_fh:
                stderr_fh.close()
            if stdin_fh:
                stdin_fh.close()
            if stdout_fh:
                stdout_fh.close()

        return exit_code
