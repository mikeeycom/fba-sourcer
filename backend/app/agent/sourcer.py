"""Agent loop for finding FBA leads.

The SourcerAgent orchestrates multi-turn conversations with Claude.
It maintains conversation history, executes tools via the registry,
and extracts qualified leads from Claude's responses.
"""

from pydantic import ValidationError

from app.clients.claude_client import ClaudeClient
from app.agent.registry import ToolRegistry
from app.agent.tools import get_tool_schemas
from app.models import Product
from app.utils.logger import get_logger

logger = get_logger(__name__)

SUBMIT_LEADS_TOOL = "submit_leads"


class SourcerAgent:
    """Agent for finding qualified FBA leads using Claude + tools.

    Uses Claude as the "brain" to orchestrate tool use:
    - Claude decides which tools to call and why
    - Agent executes tools via registry
    - Results go back to Claude for next decision
    - Continues until Claude finds 5-7 qualified leads
    """

    def __init__(self, claude_client: ClaudeClient, tool_registry: ToolRegistry):
        """Initialize agent with dependencies.

        Args:
            claude_client: Claude API client for agentic calls
            tool_registry: Registry for executing tools
        """
        self.claude_client = claude_client
        self.tool_registry = tool_registry
        self.max_iterations = 15  # Prevent runaway loops

    def run(self, category: str) -> list[Product]:
        """Find FBA leads in a category.

        Orchestrates multi-turn conversation with Claude to find 5-7 qualified leads.
        Uses web_search, keepa_query, and calculate_roi tools.

        Args:
            category: Product category to search (e.g., 'kitchen gadgets')

        Returns:
            List of Product objects meeting criteria (50+ sales, 20%+ ROI)
        """
        logger.info("Agent starting", extra={"category": category})

        # Get available tools
        tools = get_tool_schemas()

        # Initialize conversation with initial prompt
        messages = [
            {
                "role": "user",
                "content": self._build_system_prompt(category),
            }
        ]

        leads = []
        iteration = 0

        # Main loop: continue until Claude stops using tools
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(
                "Agent iteration",
                extra={"iteration": iteration, "category": category},
            )

            # Call Claude with current conversation
            response = self.claude_client.call_agent(messages, tools)

            if not response["success"]:
                logger.error(
                    "Claude call failed",
                    extra={"category": category, "iteration": iteration},
                )
                break

            # Add Claude's response to conversation history
            content = response["content"]
            messages.append({"role": "assistant", "content": content})

            # Check stop reason
            stop_reason = response["stop_reason"]
            logger.info(
                "Claude response",
                extra={
                    "iteration": iteration,
                    "stop_reason": stop_reason,
                    "has_tool_use": self._has_tool_use(content),
                },
            )

            # If Claude called submit_leads, that's the terminal action -
            # parse the structured leads and stop, regardless of any other
            # tool calls in the same turn.
            submit_block = self._find_tool_call(content, SUBMIT_LEADS_TOOL)
            if submit_block:
                logger.info(
                    "Agent submitted leads",
                    extra={"category": category, "iterations": iteration},
                )
                leads = self._parse_leads(submit_block.input)
                break

            # If Claude stopped without calling any tool (including
            # submit_leads), it gave up or ran out of things to do - there
            # are no leads to extract from free text.
            if stop_reason != "tool_use":
                logger.warning(
                    "Agent stopped without submitting leads",
                    extra={
                        "category": category,
                        "iterations": iteration,
                        "stop_reason": stop_reason,
                    },
                )
                break

            # Execute tool calls and add results back to conversation
            tool_results = self._execute_tools(content)
            if not tool_results:
                logger.warning("No tools found in response", extra={"iteration": iteration})
                break

            messages.append({"role": "user", "content": tool_results})

        logger.info(
            "Agent complete",
            extra={"category": category, "leads_found": len(leads), "iterations": iteration},
        )

        return leads

    def _build_system_prompt(self, category: str) -> str:
        """Build initial system prompt for agent.

        Instructs Claude on its role, available tools, and success criteria.

        Args:
            category: Product category to search

        Returns:
            Initial prompt string
        """
        return f"""You are an FBA (Fulfillment by Amazon) product sourcing agent.

Goal: Find 5-7 qualified product leads in the '{category}' category that meet sourcing criteria.

Criteria for qualified products:
- Estimated 50+ monthly sales (verified via Keepa)
- 20%+ ROI minimum (selling price vs cost)
- Available on Amazon
- Realistic sourcing opportunity

Available Tools:
1. web_search: Search UK retailers for products in the category
   - Use this first to find candidate products
   - Search for products in specific price ranges

2. keepa_query: Query Amazon (Keepa) for sales data and price history
   - Use ASIN to get sales rank, monthly sales estimates
   - Verify products meet 50+ monthly sales criteria

3. calculate_roi: Calculate ROI percentage
   - Input: selling price (current Amazon price) and cost price
   - Verify 20%+ ROI is achievable

4. submit_leads: Submit your final list of 5-7 qualified leads
   - Call this ONLY once every lead is validated against both criteria
   - This ends your research - do not call it alongside other tools

Sourcing Strategy:
1. Use web_search to find product candidates in '{category}'
2. For each promising product, get its ASIN
3. Use keepa_query to verify 50+ monthly sales
4. Calculate realistic cost price (usually 40-60% of selling price)
5. Use calculate_roi to confirm 20%+ ROI is possible
6. Once you have 5-7 qualified leads, call submit_leads with the full list

Start searching now for '{category}' products."""

    def _has_tool_use(self, content: list) -> bool:
        """Check if content contains tool_use blocks.

        Args:
            content: List of content blocks from Claude

        Returns:
            True if content has tool_use blocks
        """
        return any(hasattr(block, "type") and block.type == "tool_use" for block in content)

    def _find_tool_call(self, content: list, tool_name: str):
        """Find the first tool_use block matching a given tool name.

        Args:
            content: List of content blocks from Claude
            tool_name: Name of the tool to look for (e.g. 'submit_leads')

        Returns:
            The matching tool_use block, or None if not present
        """
        for block in content:
            if hasattr(block, "type") and block.type == "tool_use" and block.name == tool_name:
                return block
        return None

    def _execute_tools(self, content: list) -> list:
        """Execute tool calls from Claude response.

        Extracts tool_use blocks, executes them via registry, and formats results.

        Args:
            content: List of content blocks from Claude response

        Returns:
            List of tool_result dicts for next message to Claude
        """
        tool_results = []

        for block in content:
            # Only process tool_use blocks
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input

            logger.info(
                "Executing tool",
                extra={"tool": tool_name, "input_keys": list(tool_input.keys())},
            )

            # Execute tool via registry
            result = self.tool_registry.execute_tool(tool_name, tool_input)

            logger.info(
                "Tool executed",
                extra={"tool": tool_name, "success": result.get("success")},
            )

            # Create tool result block for Claude
            tool_result = {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            }
            tool_results.append(tool_result)

        return tool_results

    def _parse_leads(self, submit_leads_input: dict) -> list[Product]:
        """Parse and validate leads from a submit_leads tool call.

        Each lead is validated against the Product model. Invalid leads
        (e.g. Claude produced a malformed field) are logged and skipped
        rather than failing the whole batch.

        Args:
            submit_leads_input: The 'input' dict from the submit_leads tool_use block

        Returns:
            List of validated Product objects (may be fewer than submitted
            if some failed validation)
        """
        raw_leads = submit_leads_input.get("leads", [])
        leads = []

        for raw_lead in raw_leads:
            try:
                leads.append(Product(**raw_lead))
            except ValidationError as e:
                logger.warning(
                    "Skipping invalid lead from agent",
                    extra={"asin": raw_lead.get("asin"), "error": str(e)},
                )

        if len(leads) < len(raw_leads):
            logger.warning(
                "Some submitted leads failed validation",
                extra={"submitted": len(raw_leads), "valid": len(leads)},
            )

        return leads