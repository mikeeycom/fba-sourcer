"""Anthropic Claude API client wrapper."""

from anthropic import Anthropic, APIError, APIConnectionError, APITimeoutError
from app.config import settings
from app.utils.logger import get_logger
from app.utils.exceptions import APIError as AppAPIError
import time

logger = get_logger(__name__)


class ClaudeClient:
    """Wrapper around Anthropic Claude API for agent use."""

    def __init__(self, api_key: str = None):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key. If None, uses CLAUDE_API_KEY from env
        """
        self.api_key = api_key or settings.claude_api_key
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY not set in environment")

        self.client = Anthropic(api_key=self.api_key)
        logger.info("Claude client initialized")

    def call_agent(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
    ) -> dict:
        """Call Claude with tool use.

        Args:
            messages: List of messages in conversation format
            tools: List of tool definitions (schemas)
            model: Model to use
            max_tokens: Max tokens in response

        Returns:
            Response dict with content, stop_reason, usage

        Raises:
            AppAPIError: If Claude API call fails
        """
        start_time = time.time()

        try:
            logger.info(
                "Claude API call",
                extra={
                    "model": model,
                    "message_count": len(messages),
                    "tool_count": len(tools),
                },
            )

            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                tools=tools,
                messages=messages,
            )

            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                "Claude API success",
                extra={
                    "model": model,
                    "latency_ms": latency_ms,
                    "stop_reason": response.stop_reason,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

            return {
                "success": True,
                "content": response.content,
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "latency_ms": latency_ms,
            }

        except APITimeoutError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Claude API timeout",
                extra={"latency_ms": latency_ms, "error": str(e)},
            )
            raise AppAPIError(f"Claude API timeout: {str(e)}") from e

        except APIConnectionError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Claude API connection error",
                extra={"latency_ms": latency_ms, "error": str(e)},
            )
            raise AppAPIError(f"Claude API connection error: {str(e)}") from e

        except APIError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Claude API error",
                extra={
                    "latency_ms": latency_ms,
                    "status_code": e.status_code,
                    "error": str(e),
                },
            )
            raise AppAPIError(f"Claude API error: {str(e)}") from e

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Claude API unexpected error",
                extra={"latency_ms": latency_ms, "error": str(e)},
            )
            raise AppAPIError(f"Unexpected error calling Claude: {str(e)}") from e