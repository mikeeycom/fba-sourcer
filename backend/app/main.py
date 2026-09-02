"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.registry import ToolRegistry
from app.agent.sourcer import SourcerAgent
from app.clients.claude_client import ClaudeClient
from app.config import settings
from app.models import FindLeadsRequest, FindLeadsResponse, HealthResponse
from app.utils.exceptions import FBASourcingError
from app.utils.logger import get_logger

# Initialize logger
logger = get_logger(__name__, level=settings.log_level)

# Create FastAPI app
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    debug=settings.debug,
)

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent components
claude_client = ClaudeClient(api_key=settings.claude_api_key)
tool_registry = ToolRegistry()
sourcer_agent = SourcerAgent(claude_client, tool_registry)


@app.exception_handler(FBASourcingError)
async def fba_exception_handler(request, exc: FBASourcingError):
    """Handle application-specific errors gracefully."""
    logger.error("FBA error", extra={"error": str(exc), "path": request.url.path})
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(
        "Unexpected error",
        extra={
            "error": str(exc),
            "error_type": type(exc).__name__,
            "path": request.url.path,
        },
    )
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.on_event("startup")
async def startup_event():
    """Log application startup."""
    logger.info("Application startup", extra={"version": settings.app_version})


@app.on_event("shutdown")
async def shutdown_event():
    """Log application shutdown."""
    logger.info("Application shutdown")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {"message": "FBA Sourcer API"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version=settings.app_version)


@app.post("/api/find-leads", response_model=FindLeadsResponse, tags=["Agent"])
async def find_leads(request: FindLeadsRequest) -> FindLeadsResponse:
    """Find qualified FBA leads in a category.

    Orchestrates the sourcing agent to find 5-7 leads meeting criteria:
    - 50+ monthly sales (via Keepa)
    - 20%+ ROI (calculated from sourcing cost)

    The agent:
    1. Searches for products in the category
    2. Validates sales volume via Keepa
    3. Calculates ROI for each candidate
    4. Returns qualified leads

    Args:
        request: FindLeadsRequest with category to search

    Returns:
        FindLeadsResponse with list of qualified leads
    """
    try:
        logger.info("Finding leads", extra={"category": request.category})

        # Run sourcing agent
        leads = sourcer_agent.run(request.category)

        logger.info(
            "Leads found",
            extra={"category": request.category, "count": len(leads)},
        )

        return FindLeadsResponse(success=True, leads=leads)

    except Exception as e:
        logger.error(
            "Find leads failed",
            extra={"category": request.category, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=str(e))