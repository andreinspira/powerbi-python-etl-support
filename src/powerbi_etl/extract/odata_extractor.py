"""
OData extractor for Dynamics 365 / Dataverse integration.
This is a stub implementation demonstrating the pattern for Microsoft Graph / Dataverse Web API.
Actual implementation requires Azure AD app registration and valid credentials.
"""

import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union
import structlog

logger = structlog.get_logger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class ODataExtractor:
    """
    OData extractor for Dynamics 365 / Dataverse Web API.
    
    Note: This is a demonstration stub. Actual implementation requires:
    1. Azure AD App Registration with API permissions for Dynamics 365
    2. Client credentials flow (service principal) or authorization code flow
    3. Valid tenant ID, client ID, and client secret
    4. Dataverse environment URL
    
    For portfolio/demo purposes, this shows the integration pattern without
    requiring live credentials. Sample data can be generated instead.
    """
    
    def __init__(
        self,
        environment_url: str = None,
        tenant_id: str = None,
        client_id: str = None,
        client_secret: str = None,
        entity_name: str = "opportunities",
        **kwargs
    ):
        self.environment_url = environment_url or os.getenv("D365_ENV_URL")
        self.tenant_id = tenant_id or os.getenv("D365_TENANT_ID")
        self.client_id = client_id or os.getenv("D365_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("D365_CLIENT_SECRET")
        self.entity_name = entity_name
        self.kwargs = kwargs
        self._access_token = None
        self._token_expires = 0
    
    def _get_access_token(self) -> Optional[str]:
        """
        Get OAuth2 access token using client credentials flow.
        Returns None if credentials not configured (demo mode).
        """
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            logger.info("D365 credentials not configured - demo mode")
            return None
        
        if not HTTPX_AVAILABLE:
            logger.error("httpx not available for HTTP requests")
            return None
        
        # Check if cached token is still valid
        import time
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token
        
        try:
            token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": f"{self.environment_url.rstrip('/')}/.default",
            }
            
            with httpx.Client() as client:
                response = client.post(token_url, data=data, timeout=30)
                response.raise_for_status()
                token_data = response.json()
                
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires = time.time() + expires_in
                
                return self._access_token
        except Exception as e:
            logger.error("Failed to get D365 access token", error=str(e))
            return None
    
    def extract(self, filter_query: str = None, select: str = None, top: int = 5000) -> Dict[str, Any]:
        """
        Extract data from Dataverse Web API.
        
        In demo mode, returns sample data matching the expected schema.
        """
        if not self.environment_url:
            logger.info("No D365 environment configured - returning sample data")
            return self._get_sample_data()
        
        access_token = self._get_access_token()
        if not access_token:
            logger.warning("No valid access token - returning sample data")
            return self._get_sample_data()
        
        # Build OData query
        url = f"{self.environment_url.rstrip('/')}/api/data/v9.2/{self.entity_name}"
        params = {}
        if filter_query:
            params["$filter"] = filter_query
        if select:
            params["$select"] = select
        if top:
            params["$top"] = min(top, 5000)  # Dataverse max page size
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }
        
        try:
            if not HTTPX_AVAILABLE:
                return self._get_sample_data()
            
            all_records = []
            next_url = url
            
            with httpx.Client() as client:
                while next_url:
                    if next_url == url:
                        response = client.get(next_url, headers=headers, params=params, timeout=60)
                    else:
                        response = client.get(next_url, headers=headers, timeout=60)
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    records = data.get("value", [])
                    all_records.extend(records)
                    
                    next_url = data.get("@odata.nextLink")
                    
                    if not next_url or len(all_records) >= top:
                        break
            
            return {
                "success": True,
                "records": all_records[:top],
                "count": len(all_records),
                "metadata": {
                    "entity": self.entity_name,
                    "environment": self.environment_url,
                    "source": "dataverse_web_api",
                }
            }
        except Exception as e:
            logger.error("Dataverse extraction failed", error=str(e))
            return {
                "success": False,
                "records": [],
                "count": 0,
                "metadata": {},
                "error": str(e)
            }
    
    def _get_sample_data(self) -> Dict[str, Any]:
        """Generate sample Dynamics 365 opportunity data for demo."""
        import pandas as pd
        from datetime import date, timedelta
        from decimal import Decimal
        import random
        
        random.seed(42)
        n = 50
        
        statuses = ["Open", "Won", "Lost", "In Progress", "Qualified"]
        stages = ["Qualify", "Develop", "Propose", "Close"]
        
        records = []
        for i in range(n):
            created = date(2023, 1, 1) + timedelta(days=random.randint(0, 600))
            est_close = created + timedelta(days=random.randint(30, 180))
            
            status = random.choice(statuses)
            if status == "Won":
                actual_close = created + timedelta(days=random.randint(30, 200))
                probability = 100
            elif status == "Lost":
                actual_close = created + timedelta(days=random.randint(30, 150))
                probability = 0
            else:
                actual_close = None
                probability = random.choice([10, 25, 50, 75, 90])
            
            records.append({
                "opportunityid": f"OPP-{i+1:04d}",
                "name": f"Opportunity {i+1:04d} - Client {random.randint(1, 20)}",
                "statecode": 0 if status in ["Open", "In Progress", "Qualified"] else 1,
                "statuscode": status,
                "stepname": random.choice(stages),
                "estimatedvalue": round(Decimal(str(random.uniform(5000, 500000))), 2),
                "estimatedclosedate": est_close.isoformat(),
                "actualclosedate": actual_close.isoformat() if actual_close else None,
                "customerid": f"ACC-{random.randint(1, 20):03d}",
                "ownerid": f"OWN-{random.randint(1, 5):02d}",
                "probability": probability,
                "createdon": created.isoformat(),
                "modifiedon": (created + timedelta(days=random.randint(0, 100))).isoformat(),
            })
        
        return {
            "success": True,
            "records": records,
            "count": len(records),
            "metadata": {
                "entity": self.entity_name,
                "environment": self.environment_url or "demo",
                "source": "sample_data",
            }
        }
    
    def validate_connection(self) -> bool:
        """Validate connection to Dataverse."""
        if not self.environment_url:
            return True  # Demo mode always valid
        
        access_token = self._get_access_token()
        if not access_token:
            return False
        
        try:
            if not HTTPX_AVAILABLE:
                return False
            
            url = f"{self.environment_url.rstrip('/')}/api/data/v9.2/WhoAmI"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=10)
                return response.status_code == 200
        except Exception:
            return False