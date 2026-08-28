"""Agent loop for finding FBA leads.

The SourcerAgent orchestrates multi-turn conversations with Claude.
It maintains conversation history, executes tools via the registry,
and extracts qualified leads from Claude's responses.
"""

from app.clients.claude_client import ClaudeClient
from app.agent.registry import ToolRegistry
from app.agent.tools import get_tool_schemas
from app.models import Product
from app.utils.logger import get_logger

logger = get_logger(__name__)


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

            # If Claude is done (not using tools), extract leads and break
            if stop_reason != "tool_use":
                logger.info(
                    "Agent finished",
                    extra={
                        "category": category,
                        "iterations": iteration,
                        "stop_reason": stop_reason,
                    },
                )
                leads = self._extract_leads(content)
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

Sourcing Strategy:
1. Use web_search to find product candidates in '{category}'
2. For each promising product, get its ASIN
3. Use keepa_query to verify 50+ monthly sales
4. Calculate realistic cost price (usually 40-60% of selling price)
5. Use calculate_roi to confirm 20%+ ROI is possible
6. Build a list of 5-7 qualified leads

Return final results when you have found 5-7 qualified leads. Format as:
ASIN | Title | Current Price | Est. Monthly Sales | ROI% | Max Cost to Achieve 20% ROI

Start searching now for '{category}' products."""

    def _has_tool_use(self, content: list) -> bool:
        """Check if content contains tool_use blocks.

        Args:
            content: List of content blocks from Claude

        Returns:
            True if content has tool_use blocks
        """
        return any(hasattr(block, "type") and block.type == "tool_use" for block in content)

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

    def _extract_leads(self, content: list) -> list[Product]:
        """Extract leads from Claude's final response.

        Parses Claude's structured response to extract qualified products.

        Args:
            content: List of content blocks from Claude's final response

        Returns:
            List of Product objects
        """
        # For now, return empty list
        # TODO: Parse Claude's response text and extract leads
        # This would require:
        # 1. Extract text blocks from content
        # 2. Parse structured format (ASIN | Title | Price | Sales | ROI%)
        # 3. Create Product objects from parsed data
        # 4. Validate all required fields present
        #
        # Implemented in next phase after testing agent loop
        logger.info("Extracting leads from response (TODO: implement parser)")
        return []