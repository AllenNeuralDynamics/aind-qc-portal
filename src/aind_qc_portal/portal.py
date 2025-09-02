"""Portal main entrypoint"""

import panel as pn
from tornado.web import RequestHandler, HTTPError
from aind_qc_portal.portal_contents.database import Database
from aind_qc_portal.portal_contents.panel import Portal
from aind_qc_portal.utils import format_css_background

pn.extension(
    "jsoneditor", "modal", disconnect_notification="Connection lost, please reload the page!", notifications=True
)

format_css_background()

database = Database()
portal = Portal(database=database)


class UploadMetadataHandler(RequestHandler):

    def post(self):
        try:
            metadata = self.get_json_body()
            if not metadata:
                raise HTTPError(400, 'No metadata provided.')
            print("Received metadata:", metadata)  # Debugging line
            # For now, return success status. Uncomment the line below when database method is available
            # status_code = database.upload_metadata(metadata)
            status_code = 200  # Temporary success status
            self.set_header('Content-Type', 'application/json')
            self.write({'status': status_code})
        except Exception as e:
            raise HTTPError(500, f'Failed to upload metadata: {str(e)}')


ROUTES = [('/upload_metadata', UploadMetadataHandler, {})]


portal.__panel__().servable(title="QC Portal")
