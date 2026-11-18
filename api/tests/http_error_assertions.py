"""Assertions for migrating legacy endpoint fixtures to the common wire contract.

Endpoint suites still pin their status, concealment message and machine codes;
boundary tests independently exercise the status-to-code contract.
"""
from uuid import UUID


def assert_error_response(test, response, legacy):
    defaults = {
        400: ('request_invalid', 'Invalid request'),
        401: ('authentication_required', 'Authentication required'),
        403: ('access_denied', 'Access denied'),
        404: ('resource_not_found', 'Resource not found'),
        409: ('resource_conflict', 'Request conflicts with existing resources'),
        410: ('operation_disabled', 'Operation is disabled'),
        500: ('internal_error', 'Request could not be completed'),
    }
    test.assertGreaterEqual(response.status_code, 400)
    code, message = defaults[response.status_code]
    if response.status_code < 500:
        if 'error' in legacy:
            code = legacy['error']
        message = legacy.get('message', message)
    request_id = response.headers['X-Request-ID']
    UUID(request_id)
    test.assertEqual(response.json, {
        'error': {'code': code, 'message': message},
        'message': message, 'requestId': request_id,
    })
