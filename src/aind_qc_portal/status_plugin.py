"""Plugin file for /status health check endpoint for Panel server"""

import json
from tornado.web import RequestHandler
from aind_qc_portal.status import run_all_status_checks

class StatusHandler(RequestHandler):
    """Request handler for /status health check endpoint"""
    def get(self):
        try:
            results = run_all_status_checks()
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(results))
        except Exception as e:
            self.set_status(500)
            self.write(json.dumps({"status": "error", "error": str(e)}))

ROUTES = [("/status", StatusHandler, {})]

__all__ = ["ROUTES"]
