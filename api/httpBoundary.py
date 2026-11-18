"""Safe HTTP errors, request bounds and correlation; no runtime dependencies."""
import re
from uuid import uuid4
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from sqlalchemy.exc import DataError, IntegrityError

from flask import g, jsonify, request


def install_http_boundary(app):
    """Install before auth so early denials have the same server-owned ID."""
    if app.extensions.get('http_boundary_installed'):
        return
    app.extensions['http_boundary_installed'] = True
    if app.config.get('MAX_CONTENT_LENGTH') is None:
        app.config['MAX_CONTENT_LENGTH'] = 262144

    @app.before_request
    def begin_request():
        g.request_id = str(uuid4())
        if request.content_length is not None and request.content_length > app.config['MAX_CONTENT_LENGTH']:
            raise RequestEntityTooLarge()
        # Werkzeug may hand the JSON parser a truncated stream at the exact
        # limit. Read one bounded extra byte for terminated, unknown-length
        # bodies so oversize is reported as 413 rather than malformed JSON.
        if request.content_length is None and request.environ.get('wsgi.input_terminated'):
            limit = app.config['MAX_CONTENT_LENGTH']
            request.max_content_length = limit + 1
            data = request.get_data(cache=True)
            request.max_content_length = limit
            if len(data) > limit:
                raise RequestEntityTooLarge()
        if len(request.query_string) > 8192:
            return safe_error('request_invalid', 'Query string is too large', 400)

    @app.errorhandler(HTTPException)
    def framework_error(exc):
        response = exc.get_response()
        code, message = error_defaults(exc.code)
        response.set_data(app.json.dumps({'error': {'code': code, 'message': message}}))
        response.content_type = 'application/json'
        return response

    @app.errorhandler(IntegrityError)
    def integrity_error(exc):
        return safe_error('resource_conflict', 'Request conflicts with existing resources', 409)

    @app.errorhandler(DataError)
    def data_error(exc):
        return safe_error('request_invalid', 'Invalid request values', 400)

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        # Never serialize/log driver parameters, bodies, tokens or private rows.
        app.logger.error('Request failed request_id=%s exception_type=%s',
                         g.request_id, type(exc).__name__)
        return safe_error('internal_error', 'Request could not be completed', 500)

    @app.after_request
    def finalize_response(response):
        # /ready intentionally returns a fixed operational body with 503.
        readiness = getattr(g, 'operational_readiness_response', False) and response.status_code == 503
        if response.status_code >= 400 and not readiness:
            payload = response.get_json(silent=True)
            payload = payload if isinstance(payload, dict) else {}
            default_code, default_message = error_defaults(response.status_code)
            error = payload.get('error')
            code = default_code
            message = payload.get('message', default_message)
            if isinstance(error, dict):
                code = error.get('code', default_code)
                message = error.get('message', message)
            elif isinstance(error, str):
                if re.fullmatch(r'[a-z][a-z0-9_]*', error):
                    code = error
                else:
                    message = error
            if response.status_code >= 500:
                code, message = default_code, default_message
                payload = {}
            payload.update(error={'code': code, 'message': message},
                           message=message, requestId=g.request_id)
            response.set_data(app.json.dumps(payload))
            response.content_type = 'application/json'

        response.headers['X-Request-ID'] = g.request_id
        if request.headers.get('Authorization') or response.status_code >= 400:
            response.headers['Cache-Control'] = 'no-store'
        return response


def authentication_error(code):
    """Reserved for authentication denial before a domain operation executes."""
    return jsonify(error={'code': code, 'message': 'Authentication required'},
                   requestId=g.request_id), 401


def error_defaults(status):
    return {
        400: ('request_invalid', 'Invalid request'),
        401: ('authentication_required', 'Authentication required'),
        403: ('access_denied', 'Access denied'),
        404: ('resource_not_found', 'Resource not found'),
        405: ('method_not_allowed', 'Method not allowed'),
        409: ('resource_conflict', 'Request conflicts with existing resources'),
        410: ('operation_disabled', 'Operation is disabled'),
        413: ('request_too_large', 'Request body is too large'),
        415: ('media_type_unsupported', 'Expected application/json'),
        429: ('rate_limited', 'Too many requests'),
    }.get(status, ('internal_error', 'Request could not be completed')
          if status >= 500 else ('request_rejected', 'Request rejected'))


def safe_error(code, message, status):
    return jsonify(error={'code': code, 'message': message}, message=message), status
