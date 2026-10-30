"""HTTP correlation and authentication failures; no domain or database imports."""
from uuid import uuid4

from flask import g, jsonify, request


def install_http_boundary(app):
    """Install before auth so early denials have the same server-owned ID."""
    if app.extensions.get('http_boundary_installed'):
        return
    app.extensions['http_boundary_installed'] = True

    @app.before_request
    def begin_request():
        g.request_id = str(uuid4())

    @app.after_request
    def finalize_response(response):
        response.headers['X-Request-ID'] = g.request_id
        if request.headers.get('Authorization') or response.status_code >= 400:
            response.headers['Cache-Control'] = 'no-store'
        return response


def authentication_error(code):
    """Reserved for authentication denial before a domain operation executes."""
    return jsonify(error={'code': code, 'message': 'Authentication required'},
                   requestId=g.request_id), 401
