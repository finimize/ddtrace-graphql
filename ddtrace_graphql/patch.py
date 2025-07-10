"""
Tracing for the graphql-core library.

https://github.com/graphql-python/graphql-core
"""

import logging
import os

import graphql
import wrapt

# Try to import graphql.backend.core for older versions of graphql-core
try:
    import graphql.backend.core
    HAS_BACKEND_CORE = True
except ImportError:
    HAS_BACKEND_CORE = False
    logger = logging.getLogger(__name__)
    logger.debug("graphql.backend.core not available in this version of graphql-core")

# Try to import unwrap from ddtrace.util, fallback to ddtrace.internal if needed
try:
    from ddtrace.util import unwrap
    logger = logging.getLogger(__name__)
    logger.debug("Successfully imported unwrap from ddtrace.util")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import unwrap from ddtrace.util: {e}")
    try:
        from ddtrace.internal.utils.wrappers import unwrap
        logger.info("Successfully imported unwrap from ddtrace.internal.utils.wrappers")
    except ImportError as fallback_error:
        logger.error(f"Failed to import unwrap from ddtrace.internal: {fallback_error}")
        # Fallback to wrapt's unwrap functionality
        from wrapt import unwrap_function_wrapper as unwrap
        logger.info("Using wrapt.unwrap_function_wrapper as fallback")

from ddtrace_graphql.base import traced_graphql_wrapped


def patch(span_kwargs=None, span_callback=None, ignore_exceptions=()):
    """
    Monkeypatches graphql-core library to trace graphql calls execution.
    """

    def wrapper(func, _, args, kwargs):
        return traced_graphql_wrapped(
            func,
            args,
            kwargs,
            span_kwargs=span_kwargs,
            span_callback=span_callback,
            ignore_exceptions=ignore_exceptions,
        )

    logger.debug("Patching `graphql.graphql` function.")

    wrapt.wrap_function_wrapper(graphql, "graphql", wrapper)
    
    # Also patch graphql_sync if available (newer versions of graphql-core)
    if hasattr(graphql, 'graphql_sync'):
        logger.debug("Patching `graphql.graphql_sync` function.")
        wrapt.wrap_function_wrapper(graphql, "graphql_sync", wrapper)

    # Only patch execute_and_validate if graphql.backend.core is available
    if HAS_BACKEND_CORE:
        logger.debug("Patching `graphql.backend.core.execute_and_validate` function.")
        wrapt.wrap_function_wrapper(graphql.backend.core, "execute_and_validate", wrapper)
    else:
        logger.debug("Skipping `graphql.backend.core.execute_and_validate` patch - not available in this version")


def unpatch():
    logger.debug("Unpatching `graphql.graphql` function.")
    try:
        unwrap(graphql, "graphql")
        logger.debug("Successfully unpatched `graphql.graphql` function.")
    except Exception as e:
        logger.warning(f"Failed to unpatch `graphql.graphql` function: {e}")
    
    # Also unpatch graphql_sync if available
    if hasattr(graphql, 'graphql_sync'):
        logger.debug("Unpatching `graphql.graphql_sync` function.")
        try:
            unwrap(graphql, "graphql_sync")
            logger.debug("Successfully unpatched `graphql.graphql_sync` function.")
        except Exception as e:
            logger.warning(f"Failed to unpatch `graphql.graphql_sync` function: {e}")
    
    # Only unpatch execute_and_validate if graphql.backend.core is available
    if HAS_BACKEND_CORE:
        logger.debug("Unpatching `graphql.backend.core.execute_and_validate` function.")
        try:
            unwrap(graphql.backend.core, "execute_and_validate")
            logger.debug("Successfully unpatched `graphql.backend.core.execute_and_validate` function.")
        except Exception as e:
            logger.warning(f"Failed to unpatch `graphql.backend.core.execute_and_validate` function: {e}")
    else:
        logger.debug("Skipping `graphql.backend.core.execute_and_validate` unpatch - not available in this version")
