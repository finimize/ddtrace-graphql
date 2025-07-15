"""
To trace all GraphQL requests, patch the library like so::

    from ddtrace_graphql import patch
    patch()

    from graphql import graphql
    result = graphql(schema, query)


If you do not want to monkeypatch ``graphql.graphql`` function or want to trace
only certain calls you can use the ``traced_graphql`` function::

    from ddtrace_graphql import traced_graphql
    traced_graphql(schema, query)
"""


import logging

logger = logging.getLogger(__name__)

# Import required modules directly - ddtrace >= 1.5.5 support only
try:
    import graphql
    logger.debug("Successfully imported graphql module")
    
    from .base import (
        TracedGraphQLSchema, traced_graphql,
        TYPE, SERVICE, QUERY, ERRORS, INVALID, RES_NAME, DATA_EMPTY,
        CLIENT_ERROR
    )
    from .patch import patch, unpatch
    __all__ = [
        'TracedGraphQLSchema',
        'patch', 'unpatch', 'traced_graphql',
        'TYPE', 'SERVICE', 'QUERY', 'ERRORS', 'INVALID',
        'RES_NAME', 'DATA_EMPTY', 'CLIENT_ERROR',
    ]
    logger.info("Successfully initialized ddtrace-graphql")
    
except ImportError as error:
    logger.error(f"Failed to import required modules: {error}")
    logger.error("ddtrace-graphql requires ddtrace >= 1.5.5 and graphql-core")
    raise