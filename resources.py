"""
Resources blueprint — read-only "Common Drives" page (V3.1).

Currently shows two hardcoded link cards that point at external common
drives. Designed so that adding a third card later is a one-line change
to the `RESOURCES` list below — no DB schema or migration involved.
"""
from flask import Blueprint, render_template
from flask_login import login_required

resources_bp = Blueprint("resources", __name__)


# Each card: (title, description, href, bootstrap-icon name).
# Update this list to add/edit/remove cards — that's the whole "API".
RESOURCES = [
    {
        "title": "Common Drive 1",
        "description": "Shared lounge documents, forms, and reference "
                       "materials for everyday use.",
        "href": "https://example.com/common-drive-1",
        "icon": "bi-cloud-arrow-down",
    },
    {
        "title": "Common Drive 2",
        "description": "Photo archives, event recordings, and other "
                       "large media files for the lounge community.",
        "href": "https://example.com/common-drive-2",
        "icon": "bi-cloud-arrow-down",
    },
]


@resources_bp.route("/")
@login_required
def index():
    """Visible to every signed-in user (staff and students alike)."""
    return render_template("resources.html", resources=RESOURCES)
