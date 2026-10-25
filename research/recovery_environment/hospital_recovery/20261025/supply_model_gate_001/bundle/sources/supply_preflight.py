"""Prospective common scheduling preflight, not a native implementation fix.

Only currently deficient scheduling proposals are rejected before mutation.
Transfers, future obligations, patient allocation and old failure histories are
untouched. Every check/proposal is retained separately from native shortages.
"""
from copy import deepcopy

from branch_runtime import BranchProtocol, care, checkpoint, digest

NOTICE = (
    "\nCOMMON EXECUTION POLICY: Before each schedule_patient call, the runtime "
    "checks your hospital's current supplies for that service, including changes "
    "from earlier tools in the same batch. A deficient schedule is rejected "
    "without scheduling the patient, consuming supplies or adding a resource "
    "failure. Its tool result reports current stock, required quantities and "
    "deficits. Arrange supplies or another legal assignment when needed. This "
    "check does not reserve future supplies, choose actions, restrict transfers "
    "or erase past failures. Other native scheduling rules still apply."
)
POLICY = {'name': 'current_supply_schedule_preflight_v1',
          'schedule_order': 'native full-batch order', 'transfer_restriction': False,
          'future_care_reserve': False, 'denied_proposals_retained': True,
          'historical_failures_unchanged': True}


class SupplyPrompts:
    def __init__(self, original):
        self.original = original

    @property
    def control(self):
        return self.original.control

    @control.setter
    def control(self, value):
        self.original.control = value

    def get_system_prompt(self):
        return self.original.get_system_prompt() + NOTICE

    def get_user_prompt(self, agent_name, agent_context, blackboard_context):
        return self.original.get_user_prompt(agent_name, agent_context, blackboard_context)


class SupplyProtocol(BranchProtocol):
    async def environment_handle_tool_call(self, tool_name, agent_name, arguments,
                                           *, phase=None, iteration=None):
        env = self.environment
        # Existing source/phase/tool/argument handling retains precedence when
        # the request is not a recognized active execution scheduling proposal.
        if (tool_name == 'schedule_patient' and phase == 'execution' and
                not self._denied(agent_name) and agent_name in env.agents_map and
                isinstance(arguments, dict)):
            pid, index = arguments.get('patient_id'), arguments.get('step_index')
            info = env.agents_map[agent_name]
            if (isinstance(pid, str) and pid in env.patients and type(index) is int and
                    0 <= index < len(env.patients[pid]['pathway']) and
                    env.patients[pid]['pathway'][index]['service'] == info['service']):
                hospital = info['hospital']
                required = deepcopy(env.consumption_map[info['service']])
                stock = {resource: env.inventory[hospital].get(resource, 0) for resource in required}
                deficits = {resource: amount - stock[resource] for resource, amount in required.items()
                            if stock[resource] < amount}
                self.supply_checks.append({'actor': agent_name, 'patient_id': pid,
                    'step_index': index, 'phase': phase, 'iteration': iteration,
                    'required': required, 'stock': stock, 'deficits': deficits,
                    'decision': 'deny' if deficits else 'delegate_native'})
                if deficits:
                    before = checkpoint(env)
                    result = {'status': 'denied', 'error': 'current supply preflight',
                              'patient_id': pid, 'step_index': index, 'hospital': hospital,
                              'required': required, 'stock': stock, 'deficits': deficits,
                              'state_changed': False}
                    self._record_tool_event(tool_name=tool_name, agent_name=agent_name,
                        arguments=deepcopy(arguments), result=deepcopy(result),
                        phase=phase, iteration=iteration)
                    joint, local = env._calculate_makespan_and_flow()
                    after = checkpoint(env)
                    assert digest(before) == digest(after)
                    self.observations.append({'actor': agent_name, 'tool': tool_name,
                        'arguments': deepcopy(arguments), 'phase': phase, 'status': 'denied',
                        'argument_flags': [], 'native_error': result['error'],
                        'decision_source': POLICY['name'], 'actual_state_changed': False,
                        'before': before, 'after': after, 'joint_reward': joint,
                        'local_sum': sum(local.values()), 'scoring_error': None, 'care': care(env)})
                    return result
        return await super().environment_handle_tool_call(tool_name, agent_name, arguments,
                                                         phase=phase, iteration=iteration)


def attach(branch):
    if type(branch.protocol) is not BranchProtocol:
        raise ValueError('preflight prototype requires the audited plain BranchProtocol')
    protocol = SupplyProtocol(branch.boards, deepcopy(branch.protocol.obligations),
                              policy=branch.protocol.policy)
    protocol.__dict__.update(branch.protocol.__dict__)
    protocol.supply_checks = []
    branch.protocol = branch.env.communication_protocol = protocol
    branch.env.prompts = SupplyPrompts(branch.env.prompts)
    return branch
