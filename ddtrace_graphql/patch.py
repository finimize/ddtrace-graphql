"""
Tracing for the graphql-core library.

https://github.com/graphql-python/graphql-core
"""

import logging

import graphql
import wrapt
from ddtrace.internal.utils.wrappers import unwrap

from ddtrace_graphql.base import traced_graphql_wrapped

logger = logging.getLogger(__name__)


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


def unpatch():
    """
    Unpatches the graphql-core library to remove tracing.
    """
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