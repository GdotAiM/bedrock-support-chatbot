"""Customer support chatbot - local Python prototype of an Amazon Bedrock Flows workflow.

The pipeline mirrors a Bedrock Flow exactly:

    Prompt(ClassifyMessage) -> Condition(RouteByCategory) -> one of
        Agent(BugReport with tool use) | Prompt(FAQ) | Prompt(HumanSupport)

Every module here maps 1:1 to a Bedrock Flows node; see
``MIGRATE_TO_BEDROCK_FLOWS.md`` and ``bedrock/flow_definition.json``.
"""

from .flow import FlowResult, SupportChatbotFlow
from .llm import get_llm

__all__ = ["FlowResult", "SupportChatbotFlow", "get_llm"]
__version__ = "0.1.0"