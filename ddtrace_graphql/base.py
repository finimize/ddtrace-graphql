import logging
import os

import ddtrace
import graphql
# Try to import errors from new location, fallback to old location
try:
    from ddtrace import constants as ddtrace_errors
except ImportError:
    try:
        from ddtrace.ext import errors as ddtrace_errors
    except ImportError:
        # Create dummy error constants for testing
        class ddtrace_errors:
            ERROR_STACK = "error.stack"
            ERROR_MSG = "error.msg"
            ERROR_TYPE = "error.type"

from ddtrace_graphql import utils

logger = logging.getLogger(__name__)
_graphql = graphql.graphql


TYPE = 'graphql'
QUERY = 'query'
ERRORS = 'errors'
INVALID = 'invalid'
CLIENT_ERROR = 'client_error'
DATA_EMPTY = 'data_empty'
RES_NAME = 'graphql.graphql'
#
SERVICE_ENV_VAR = 'DDTRACE_GRAPHQL_SERVICE'
SERVICE = 'graphql'


class TracedGraphQLSchema(graphql.GraphQLSchema):
    def __init__(self, *args, **kwargs):
        if 'datadog_tracer' in kwargs:
            self.datadog_tracer = kwargs.pop('datadog_tracer')
            logger.debug(
                'For schema %s using own tracer %s',
                self, self.datadog_tracer)
        super(TracedGraphQLSchema, self).__init__(*args, **kwargs)


def traced_graphql_wrapped(
    func,
    args,
    kwargs,
    span_kwargs=None,
    span_callback=None,
    ignore_exceptions=(),
):
    """
    Wrapper for graphql.graphql function.
    """
    logger.debug(f"traced_graphql_wrapped called with func={func}, args={args[:1]}")
    # allow schemas their own tracer with fall-back to the global
    schema = args[0]
    tracer = getattr(schema, 'datadog_tracer', ddtrace.tracer)
    logger.debug(f"Using tracer: {tracer}, enabled: {tracer.enabled}")

    if not tracer.enabled:
        return func(*args, **kwargs)

    query = utils.get_query_string(args, kwargs)

    _span_kwargs = {
        'name': RES_NAME,
        'span_type': TYPE,
        'service': os.getenv(SERVICE_ENV_VAR, SERVICE),
        'resource': utils.resolve_query_res(query)
    }
    _span_kwargs.update(span_kwargs or {})

    import asyncio
    
    result = func(*args, **kwargs)
    
    # Handle async results
    if asyncio.iscoroutine(result):
        async def trace_async():
            with tracer.trace(**_span_kwargs) as span:
                span.set_tag(QUERY, query)
                try:
                    actual_result = await result
                    return actual_result
                finally:
                    if 'actual_result' in locals():
                        _process_result(actual_result, span, ignore_exceptions, span_callback)
                    else:
                        span.error = 1
        
        return trace_async()
    else:
        # Handle sync results
        with tracer.trace(**_span_kwargs) as span:
            span.set_tag(QUERY, query)
            try:
                return result
            finally:
                _process_result(result, span, ignore_exceptions, span_callback)


def _process_result(result, span, ignore_exceptions, span_callback):
    """Process the result and update the span accordingly."""
    if result is not None:
        span.error = 0
        if hasattr(result, 'errors') and result.errors:
            span.set_tag(
                ERRORS,
                utils.format_errors(result.errors))
            span.set_tag(
                ddtrace_errors.ERROR_STACK,
                utils.format_errors_traceback(result.errors))
            span.set_tag(
                ddtrace_errors.ERROR_MSG,
                utils.format_errors_msg(result.errors))
            span.set_tag(
                ddtrace_errors.ERROR_TYPE,
                utils.format_errors_type(result.errors))

            span.error = int(utils.is_server_error(
                result,
                ignore_exceptions,
            ))

        span.set_metric(
            CLIENT_ERROR,
            int(bool(not span.error and result.errors))
        )
        span.set_metric(INVALID, int(getattr(result, 'invalid', 0)))
        span.set_metric(DATA_EMPTY, int(getattr(result, 'data', None) is None))
    else:
        span.error = 1

    if span_callback is not None:
        span_callback(result=result, span=span)


def traced_graphql(
    *args,
    span_kwargs=None,
    span_callback=None,
    ignore_exceptions=(),
    **kwargs
):
    return traced_graphql_wrapped(
        _graphql, args, kwargs,
        span_kwargs=span_kwargs,
        span_callback=span_callback,
        ignore_exceptions=ignore_exceptions
    )
