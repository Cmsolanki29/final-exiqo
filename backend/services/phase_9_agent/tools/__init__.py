"""Tool registry for the Phase 9 investigation agent.

Each tool is a small unit that the LLM can invoke via OpenAI-compatible
function calling.  Tools must return ``ToolOutput`` and never leak PII —
all tool outputs are passed through ``pii_redactor.redact_dict`` before
being handed back to the model.
"""

from services.phase_9_agent.tools.base_tool import BaseTool, ToolOutput
from services.phase_9_agent.tools.user_history_tool import UserHistoryTool
from services.phase_9_agent.tools.merchant_lookup_tool import MerchantLookupTool
from services.phase_9_agent.tools.fraud_pattern_tool import FraudPatternTool
from services.phase_9_agent.tools.geo_velocity_tool import GeoVelocityTool
from services.phase_9_agent.tools.blacklist_tool import BlacklistTool
from services.phase_9_agent.tools.shap_context_tool import ShapContextTool


def default_tools() -> list[BaseTool]:
    """Return one instance of each tool.  Used by the agent at construction."""
    return [
        UserHistoryTool(),
        MerchantLookupTool(),
        FraudPatternTool(),
        GeoVelocityTool(),
        BlacklistTool(),
        ShapContextTool(),
    ]


__all__ = [
    "BaseTool",
    "ToolOutput",
    "UserHistoryTool",
    "MerchantLookupTool",
    "FraudPatternTool",
    "GeoVelocityTool",
    "BlacklistTool",
    "ShapContextTool",
    "default_tools",
]
