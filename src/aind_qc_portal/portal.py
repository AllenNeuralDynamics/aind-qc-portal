"""Portal main entrypoint"""

from aind_qc_portal.portal.database import Database
from aind_qc_portal.portal.panel import Portal


portal = Portal()

portal.__panel__().servable(title=f"QC Portal")
