#!/usr/bin/env python3
"""
FastAPI application for handling eBay OAuth callbacks and web endpoints.
"""

import os
import sys
import base64
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Query, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import httpx
import uvicorn
import asyncio
from datetime import datetime
import json

from src.config import settings
from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger
from src.orchestrator import ListingOrchestrator

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Draft Maker API",
    description="eBay Draft Maker OAuth and API endpoints",
    version="1.0.0"
)

# eBay OAuth endpoints (Production)
EBAY_AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
REDIRECT_URI = "https://draft-maker-541660382374.us-west1.run.app/oauth/callback"

# Store for batch job status (in production, use database)
batch_jobs = {}

# Pydantic models for request/response
class BatchProcessRequest(BaseModel):
    gcs_path: str  # Format: gs://bucket/file.txt
    create_drafts: bool = True
    test_mode: bool = False

class BatchJobStatus(BaseModel):
    job_id: str
    status: str  # pending, running, completed, failed
    gcs_path: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_upcs: Optional[int] = None
    successful: Optional[int] = None
    failed: Optional[int] = None
    error: Optional[str] = None
    results: Optional[dict] = None


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Health check and welcome endpoint.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Draft Maker - eBay OAuth Service</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                border-bottom: 2px solid #007bff;
                padding-bottom: 10px;
            }
            .status {
                background: #d4edda;
                color: #155724;
                padding: 10px;
                border-radius: 5px;
                margin: 20px 0;
            }
            .info {
                background: #f8f9fa;
                padding: 15px;
                border-left: 4px solid #007bff;
                margin: 20px 0;
            }
            code {
                background: #f1f1f1;
                padding: 2px 5px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Draft Maker OAuth Service</h1>
            <div class="status">✅ Service is running</div>
            <div class="info">
                <h2>OAuth Setup Instructions</h2>
                <p>To authorize the application with eBay:</p>
                <ol>
                    <li>Visit <a href="/oauth/authorize">/oauth/authorize</a> to start the OAuth flow</li>
                    <li>Log in with your eBay account</li>
                    <li>Grant the requested permissions</li>
                    <li>You'll be redirected back and tokens will be stored</li>
                </ol>
            </div>
            <div class="info">
                <h2>API Endpoints</h2>
                <ul>
                    <li><code>GET /</code> - This page (health check)</li>
                    <li><code>GET /oauth/authorize</code> - Start OAuth authorization</li>
                    <li><code>GET /oauth/callback</code> - OAuth callback (automatic)</li>
                    <li><code>GET /oauth/status</code> - Check token status</li>
                    <li><code>POST /api/batch/process</code> - Trigger batch processing</li>
                    <li><code>GET /api/batch/status/{job_id}</code> - Check batch job status</li>
                    <li><code>GET /api/batch/jobs</code> - List all batch jobs</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content


@app.get("/oauth/authorize")
async def oauth_authorize():
    """
    Generate and redirect to the eBay OAuth authorization URL.
    """
    params = {
        "client_id": settings.ebay_app_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory",
        "prompt": "login"
    }
    
    # Build the authorization URL
    auth_url = f"{EBAY_AUTH_URL}?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    logger.info(f"Generated OAuth authorization URL: {auth_url}")
    
    # Return a redirect response
    return JSONResponse(
        content={
            "message": "Please visit the authorization URL",
            "authorization_url": auth_url
        },
        headers={
            "Location": auth_url
        },
        status_code=302
    )


@app.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: Optional[str] = Query(None, description="Authorization code from eBay"),
    state: Optional[str] = Query(None, description="State parameter for security"),
    error: Optional[str] = Query(None, description="Error from eBay if authorization failed"),
    error_description: Optional[str] = Query(None, description="Error description")
):
    """
    Handle OAuth callback from eBay with authorization code.
    """
    # Check for errors from eBay
    if error:
        logger.error(f"OAuth authorization failed: {error} - {error_description}")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authorization Failed</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        max-width: 600px;
                        margin: 50px auto;
                        padding: 20px;
                    }}
                    .error {{
                        background: #f8d7da;
                        color: #721c24;
                        padding: 15px;
                        border-radius: 5px;
                        border: 1px solid #f5c6cb;
                    }}
                </style>
            </head>
            <body>
                <h1>❌ Authorization Failed</h1>
                <div class="error">
                    <strong>Error:</strong> {error}<br>
                    <strong>Description:</strong> {error_description or 'No description provided'}
                </div>
                <p><a href="/oauth/authorize">Try again</a></p>
            </body>
            </html>
            """,
            status_code=400
        )
    
    # Check if we have an authorization code
    if not code:
        logger.error("No authorization code received in callback")
        raise HTTPException(status_code=400, detail="No authorization code provided")
    
    logger.info(f"Received authorization code: {code[:10]}...")
    
    try:
        # Exchange authorization code for tokens
        tokens = await exchange_code_for_tokens(code)
        
        # Store tokens using TokenManager
        token_manager = get_token_manager()
        await token_manager.set_initial_ebay_token(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens["expires_in"]
        )
        
        logger.info("Successfully stored eBay tokens")
        
        # Return success page
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authorization Successful</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                        max-width: 600px;
                        margin: 50px auto;
                        padding: 20px;
                        background: #f5f5f5;
                    }
                    .container {
                        background: white;
                        padding: 30px;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }
                    .success {
                        background: #d4edda;
                        color: #155724;
                        padding: 15px;
                        border-radius: 5px;
                        border: 1px solid #c3e6cb;
                        margin: 20px 0;
                    }
                    h1 {
                        color: #28a745;
                    }
                    .info {
                        background: #f8f9fa;
                        padding: 15px;
                        border-left: 4px solid #28a745;
                        margin: 20px 0;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✅ Authorization Successful!</h1>
                    <div class="success">
                        <strong>eBay tokens have been successfully stored.</strong><br>
                        The application can now access eBay APIs on your behalf.
                    </div>
                    <div class="info">
                        <h3>What's Next?</h3>
                        <p>The Draft Maker application is now authorized to:</p>
                        <ul>
                            <li>Create draft listings on eBay</li>
                            <li>Manage inventory</li>
                            <li>Access selling APIs</li>
                        </ul>
                        <p>You can now run the batch processing to create draft listings from UPC codes.</p>
                    </div>
                    <p><a href="/">Back to home</a> | <a href="/oauth/status">Check token status</a></p>
                </div>
            </body>
            </html>
            """,
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Failed to exchange authorization code: {str(e)}")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Token Exchange Failed</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        max-width: 600px;
                        margin: 50px auto;
                        padding: 20px;
                    }}
                    .error {{
                        background: #f8d7da;
                        color: #721c24;
                        padding: 15px;
                        border-radius: 5px;
                        border: 1px solid #f5c6cb;
                    }}
                </style>
            </head>
            <body>
                <h1>❌ Token Exchange Failed</h1>
                <div class="error">
                    <strong>Error:</strong> {str(e)}
                </div>
                <p>Please check the logs for more details.</p>
                <p><a href="/oauth/authorize">Try again</a></p>
            </body>
            </html>
            """,
            status_code=500
        )


@app.get("/oauth/status")
async def oauth_status():
    """
    Check the status of stored OAuth tokens.
    """
    try:
        token_manager = get_token_manager()
        
        # Try to get the token data from storage
        token_data = await token_manager._get_token_from_firestore("ebay")
        
        if not token_data:
            return JSONResponse(
                content={
                    "status": "not_configured",
                    "message": "No eBay tokens found. Please authorize the application first.",
                    "authorize_url": "/oauth/authorize"
                },
                status_code=404
            )
        
        # Check if token is valid
        is_valid = token_manager._is_token_still_valid(token_data)
        expires_at = token_data.get("expires_at")
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        # Convert Firestore timestamp to datetime if needed
        if hasattr(expires_at, '_seconds'):
            expires_at = datetime.fromtimestamp(expires_at._seconds)
        
        return JSONResponse(
            content={
                "status": "configured",
                "token_valid": is_valid,
                "has_refresh_token": "refresh_token" in token_data and token_data["refresh_token"],
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": token_data.get("created_at", "").isoformat() if token_data.get("created_at") else None,
                "message": "Tokens are configured and valid" if is_valid else "Token expired but can be refreshed"
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Failed to check token status: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Failed to check token status: {str(e)}"
            },
            status_code=500
        )


async def exchange_code_for_tokens(authorization_code: str) -> dict:
    """
    Exchange authorization code for access and refresh tokens.
    
    Args:
        authorization_code: The authorization code from eBay
        
    Returns:
        Token response from eBay
    """
    # Prepare credentials
    credentials = f"{settings.ebay_app_id}:{settings.ebay_cert_id}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(EBAY_TOKEN_URL, headers=headers, data=data)
        
        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.text}")
            raise Exception(f"Failed to exchange code for tokens: {response.status_code} - {response.text}")
            
    return response.json()


@app.post("/api/batch/process", response_model=BatchJobStatus)
async def trigger_batch_processing(
    request: BatchProcessRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger batch processing of UPC codes from a GCS file.
    
    Args:
        request: Batch process request with GCS path
        background_tasks: FastAPI background tasks handler
        
    Returns:
        Batch job status with job ID for tracking
    """
    # Validate GCS path format
    if not request.gcs_path.startswith("gs://"):
        raise HTTPException(
            status_code=400,
            detail="Invalid GCS path. Must start with gs://"
        )
    
    # Generate job ID
    job_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(batch_jobs)}"
    
    # Create job status
    job_status = BatchJobStatus(
        job_id=job_id,
        status="pending",
        gcs_path=request.gcs_path,
        started_at=datetime.now()
    )
    
    # Store job status
    batch_jobs[job_id] = job_status.dict()
    
    # Add background task to process batch
    background_tasks.add_task(
        run_batch_processing_task,
        job_id,
        request.gcs_path,
        request.create_drafts,
        request.test_mode
    )
    
    logger.info(f"Batch job {job_id} queued for processing: {request.gcs_path}")
    
    return job_status


@app.get("/api/batch/status/{job_id}", response_model=BatchJobStatus)
async def get_batch_job_status(job_id: str):
    """
    Get the status of a batch processing job.
    
    Args:
        job_id: The job ID to check
        
    Returns:
        Current status of the batch job
    """
    if job_id not in batch_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    return BatchJobStatus(**batch_jobs[job_id])


@app.get("/api/batch/jobs")
async def list_batch_jobs(
    limit: int = Query(10, description="Number of jobs to return"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    List all batch processing jobs.
    
    Args:
        limit: Maximum number of jobs to return
        status: Optional status filter
        
    Returns:
        List of batch jobs
    """
    jobs = list(batch_jobs.values())
    
    # Filter by status if provided
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    
    # Sort by started_at descending (newest first)
    jobs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    
    # Limit results
    jobs = jobs[:limit]
    
    return {
        "total": len(batch_jobs),
        "filtered": len(jobs),
        "jobs": jobs
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }


def run_batch_processing_task(
    job_id: str,
    gcs_path: str,
    create_drafts: bool,
    test_mode: bool
):
    """
    Background task to run batch processing.
    Note: This is a sync function that will be run in a thread pool.
    
    Args:
        job_id: The job ID for tracking
        gcs_path: GCS path to the UPC file
        create_drafts: Whether to create eBay drafts
        test_mode: Whether to run in test mode
    """
    logger.info(f"Starting batch processing job {job_id}")
    
    # Update job status to running
    batch_jobs[job_id]["status"] = "running"
    
    try:
        # Initialize orchestrator
        orchestrator = ListingOrchestrator()
        
        # Run batch processing using asyncio.run() to handle async in sync context
        results = asyncio.run(orchestrator.process_batch(
            input_source=gcs_path,
            create_drafts=create_drafts,
            save_results=True,
            is_gcs=True
        ))
        
        # Update job status with results
        batch_jobs[job_id].update({
            "status": "completed",
            "completed_at": datetime.now(),
            "total_upcs": results.get("total_upcs", 0),
            "successful": results.get("successful", 0),
            "failed": results.get("failed", 0),
            "results": results
        })
        
        logger.info(f"Batch job {job_id} completed with {results.get('successful', 0)} successful and {results.get('failed', 0)} failed")
        
    except Exception as e:
        logger.error(f"Batch job {job_id} failed with error: {str(e)}", exc_info=True)
        batch_jobs[job_id].update({
            "status": "failed",
            "completed_at": datetime.now(),
            "error": str(e)
        })


if __name__ == "__main__":
    # Run the FastAPI application
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
