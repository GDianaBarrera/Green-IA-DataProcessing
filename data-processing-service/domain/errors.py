class ServiceError(RuntimeError):
    status = 503
    code = "SOURCE_UNAVAILABLE"


class InvalidQuery(ServiceError, ValueError):
    status = 422
    code = "INVALID_QUERY"


class InvalidResponse(ServiceError):
    status = 502
    code = "UPSTREAM_INVALID_RESPONSE"


class SourceTimeout(ServiceError):
    status = 504
    code = "SOURCE_TIMEOUT"


class SourceForbidden(ServiceError):
    code = "SOURCE_ACCESS_DENIED"


class SourceNotConfigured(ServiceError):
    code = "SOURCE_NOT_CONFIGURED"
