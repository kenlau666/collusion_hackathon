"""Equal memo-read interfaces composed with the common supply preflight."""
import memo_delivery as memo
import supply_preflight as supply

ORIGINAL_ATTACH = memo.attach


class SupplyMemoProtocol(supply.SupplyProtocol, memo.MemoProtocol):
    """Cooperative MRO: supply scheduling, memo reads, native branch handling."""


def attach(branch, content, mode, *, exclude_sources=False):
    branch = ORIGINAL_ATTACH(branch, content, mode, exclude_sources=exclude_sources)
    original = branch.protocol
    protocol = SupplyMemoProtocol(branch.boards, branch.memo_id, mode,
                                  obligations=original.obligations)
    protocol.__dict__.update(original.__dict__)
    protocol.supply_checks = []
    branch.protocol = branch.env.communication_protocol = protocol
    branch.env.prompts = supply.SupplyPrompts(branch.env.prompts)
    return branch
