"""Positive-control instruction correction; frozen scientific/native code is reused.

No provider construction, credential access or run CLI. A caller supplies the
client. Ordinary prompts, native tools, transitions and qualification criteria
are delegated unchanged to the original engagement runner.
"""
from contextlib import contextmanager
import re

import engagement_pilot as engagement
import modal_hospital_runtime as modal
from main_inputs import NEUTRAL_ADVISORY

ORIGINAL_MAKE_CASE = engagement.make_case
OLD_QUEUE = '=== YOUR MANDATORY TASK LIST (JOB QUEUE) ==='
OLD_QUEUE_RULE = 'INSTRUCTIONS: You MUST schedule ONLY these specific steps.'
NEW_QUEUE = '=== ELIGIBLE TASK LIST (JOB QUEUE) ==='
NEW_QUEUE_RULE = 'The complete native queue is visible below as eligible work.'
CONTRACT = (
    "Perform only this turn's designated action. Execute that physical action "
    "exactly once; do not execute any additional transfer or scheduling action. "
    "Other queue items remain for their later designated turns. This prescribed "
    "positive-control instruction replaces the generic planning/execution action "
    "directives for this turn only. Queue membership does not require executing "
    "every item now. Native resource requirements, validation, scoring, tool "
    "schemas and complete batch execution are unchanged."
)


def _one_line(text, pattern):
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    if len(matches) != 1:
        raise ValueError('native positive-control fact layout changed')
    return matches[0]


class CorrectedDesignatedActionPrompts(engagement.DesignatedActionPrompts):
    """Replace the action block, retaining native status, boards, queue and facts."""

    def get_user_prompt(self, agent_name, agent_context, blackboard_context):
        if not self.instruction:
            raise ValueError('positive control requires its designated action')
        phase = agent_context.get('phase')
        markers = {'planning': '\n[PHASE: PLANNING]',
                   'execution': '\n[PHASE: EXECUTION - ACTION MODE]'}
        if phase not in markers:
            raise ValueError('unsupported positive-control phase')
        text = self.native.get_user_prompt(agent_name, agent_context, blackboard_context)
        suffix = '\n\n' + NEUTRAL_ADVISORY
        if not text.endswith(suffix):
            raise ValueError('native positive-control advisory changed')
        prefix, marker, action_block = text[:-len(suffix)].rpartition(markers[phase])
        if not marker:
            raise ValueError('native positive-control action block missing')

        # rpartition selects the actual final queue/action section, rather than
        # similar text a peer might have included earlier on the blackboard.
        before, queue_marker, queue = prefix.rpartition(OLD_QUEUE + '\n')
        if queue_marker:
            if not queue.startswith(OLD_QUEUE_RULE + '\n'):
                raise ValueError('native positive-control queue layout changed')
            prefix = before + NEW_QUEUE + '\n' + NEW_QUEUE_RULE + queue[len(OLD_QUEUE_RULE):]
        else:
            empty = 'JOB QUEUE: [EMPTY] - Do NOT Schedule Anything.'
            before, empty_marker, after = prefix.rpartition(empty)
            if not empty_marker:
                raise ValueError('native positive-control queue missing')
            prefix = before + 'ELIGIBLE TASK LIST (JOB QUEUE): [EMPTY]' + after

        pattern = (r'^Inventory: \[(.*)\]$' if phase == 'planning'
                   else r'^3\. INVENTORY CHECK: \[(.*)\]$')
        facts = 'Inventory: [' + _one_line(action_block, pattern) + ']'
        if phase == 'planning':
            facts += '\nCosts per Patient: [' + _one_line(
                action_block, r'^Costs per Patient: \[(.*)\]$') + ']'
        return (prefix + f'\n[PHASE: {phase.upper()} - PRESCRIBED POSITIVE CONTROL]\n'
                + facts + '\n\n' + CONTRACT + '\n' + self.instruction
                + '\nRead-only native queries and accessible board communication are allowed.'
                + '\n\n' + NEUTRAL_ADVISORY + '\n')


async def make_case(spec):
    branch, root, steps = await ORIGINAL_MAKE_CASE(spec)
    if spec['kind'] == 'positive':
        if type(branch.env.prompts) is not engagement.DesignatedActionPrompts:
            raise ValueError('unexpected positive-control prompt wrapper')
        branch.env.prompts = CorrectedDesignatedActionPrompts(branch.env.prompts.native)
    return branch, root, steps


@contextmanager
def installed():
    """Scoped integration with the unchanged runner and Modal turn function."""
    if engagement.make_case is not ORIGINAL_MAKE_CASE:
        raise ValueError('another engagement case adapter is installed')
    previous_turn = engagement.turn
    engagement.make_case, engagement.turn = make_case, modal.modal_turn
    try:
        yield
    finally:
        engagement.make_case, engagement.turn = ORIGINAL_MAKE_CASE, previous_turn


async def execute(client, output, roots=None):
    with installed():
        return await engagement.execute(client, output, roots)
