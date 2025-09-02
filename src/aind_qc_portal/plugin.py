"""Plugin file for custom Panel server endpoints"""

import json
from tornado.web import RequestHandler, HTTPError


class UploadMetadataHandler(RequestHandler):

    def post(self):
        try:
            # Parse JSON from request body
            if self.request.body:
                metadata = json.loads(self.request.body)
            else:
                metadata = None
                
            if not metadata:
                raise HTTPError(400, 'No metadata provided.')
            print("Received metadata:", metadata)  # Debugging line
            # For now, return success status. Database integration can be added later
            status_code = 200  # Temporary success status
            self.set_header('Content-Type', 'application/json')
            self.write({'status': status_code})
        except json.JSONDecodeError:
            raise HTTPError(400, 'Invalid JSON in request body.')
        except Exception as e:
            raise HTTPError(500, f'Failed to upload metadata: {str(e)}')


ROUTES = [('/upload_metadata', UploadMetadataHandler, {})]

# Export ROUTES for Panel server to discover
__all__ = ['ROUTES']
