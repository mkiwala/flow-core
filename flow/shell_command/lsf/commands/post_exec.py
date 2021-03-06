from flow import exit_codes
from flow.commands.base import CommandBase
from flow.configuration.inject.broker import BrokerConfiguration
from flow.configuration.inject.orchestrator import OrchestratorConfiguration
from flow.util.exit import exit_process
from injector import inject

import flow.interfaces
import logging
import os


LOG = logging.getLogger(__name__)


@inject(orchestrator=flow.interfaces.IOrchestrator)
class LsfPostExecCommand(CommandBase):
    injector_modules = [
            BrokerConfiguration,
            OrchestratorConfiguration,
    ]

    @staticmethod
    def annotate_parser(parser):
        parser.add_argument('--color', type=int)
        parser.add_argument('--color-group-idx', type=int)
        parser.add_argument('--execute-failure', '-f', type=int)
        parser.add_argument('--execute-success', '-s', type=int)
        parser.add_argument('--net-key', '-n')

    def _execute(self, parsed_arguments):
        LOG.info("Begin LSF post exec")

        stat = os.environ.get('LSB_JOBEXIT_STAT', None)
        if stat is None:
            LOG.critical("LSB_JOBEXIT_STAT environment variable wasn't "
                    "set... exiting!")
            exit_process(exit_codes.EXECUTE_ERROR)
        else:
            stat = int(stat)

        # we don't currently do migrating/checkpointing/requing so we're not
        # going to check for those posibilities.  Instead we will assume that
        # the job has failed.
        if stat != 0:
            exit_code = stat >> 8
            signal_number = stat & 255
            token_data = {
                'exit_code': exit_code,
                'signal_number': signal_number,
            }

            LOG.debug('Job exitted with code (%s) and signal (%s)',
                    exit_code, signal_number)

            info = os.environ.get('LSB_JOBEXIT_INFO', None)
            if info:
                LOG.info('Job exitted with LSF info: %s', info)

            deferred = self.orchestrator.create_token(
                    net_key=parsed_arguments.net_key,
                    place_idx=parsed_arguments.execute_failure,
                    color=parsed_arguments.color,
                    color_group_idx=parsed_arguments.color_group_idx,
                    data=token_data)

        else:
            LOG.debug("Process exited normally")
            deferred = self.orchestrator.create_token(
                    net_key=parsed_arguments.net_key,
                    place_idx=parsed_arguments.execute_success,
                    color=parsed_arguments.color,
                    color_group_idx=parsed_arguments.color_group_idx)

        return deferred

    def _teardown(self, parsed_arguments):
        LOG.info('End LSF post exec')
