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
import sys

logger = logging.getLogger(__name__)

# Try to import ddtrace.contrib.util for backwards compatibility
try:
    from ddtrace.contrib.util import require_modules
    logger.debug("Successfully imported ddtrace.contrib.util.require_modules")
    
    required_modules = ['graphql']
    
    with require_modules(required_modules) as missing_modules:
        if not missing_modules:
            logger.debug("All required modules available, importing ddtrace-graphql components")
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
        else:
            logger.warning(f"Missing required modules: {missing_modules}")
            
except ImportError as e:
    logger.warning(f"Failed to import ddtrace.contrib.util.require_modules: {e}")
    logger.info("Attempting direct import fallback for ddtrace >= 1.0.0")
    
    # Fallback for ddtrace >= 1.0.0 where contrib.util was removed
    try:
        import graphql
        logger.debug("Successfully imported graphql module directly")
        
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
        logger.info("Successfully initialized ddtrace-graphql with direct imports")
        
    except ImportError as fallback_error:
        logger.error(f"Failed to import required modules in fallback: {fallback_error}")
        logger.error(f"Python path: {sys.path}")
        logger.error("ddtrace-graphql will not be available")
        # Don't raise - let the application continue without GraphQL tracing

