import json
import re
import traceback
from io import StringIO

from graphql.error import GraphQLError
try:
    # graphql-core 3.x
    from graphql import DocumentNode
except ImportError:
    # graphql-core 2.x
    from graphql.language.ast import Document as DocumentNode


def format_error(error):
    """Format a GraphQLError for newer graphql-core versions."""
    if hasattr(error, 'formatted'):
        return error.formatted
    elif hasattr(error, 'message'):
        return {"message": str(error.message)}
    else:
        return {"message": str(error)}


def get_request_string(args, kwargs):
    """
    Given ``args``, ``kwargs`` of original function, returns request string.
    """
    return args[1] if len(args) > 1 else kwargs.get('request_string') or kwargs.get('source')


def get_query_string(args, kwargs):
    """
    Given ``args``, ``kwargs`` of original function, returns query as string.
    """
    rs = get_request_string(args, kwargs)
    return rs.loc.source.body if isinstance(rs, DocumentNode) else rs


def is_server_error(result, ignore_exceptions):
    """
    Determines from ``result`` if server error occured.

    Based on error handling done here https://bit.ly/2JamxWF
    """
    errors = None if result.errors is None else [
        error for error in result.errors
        if not isinstance(original_error(error), ignore_exceptions)
    ]
    
    # Determine if result is invalid (newer graphql-core compatibility)
    invalid_value = getattr(result, 'invalid', None)
    if invalid_value is None:
        # For newer graphql-core: invalid if there are errors and no data
        invalid_value = bool(result.errors and result.data is None)
    
    return bool(
        (
            errors
            and not invalid_value
        )
        or
        (
            errors
            and invalid_value
            and len(result.errors) == 1
            and not isinstance(result.errors[0], GraphQLError)
        )
    )


def original_error(err):
    """
    Returns original exception from graphql exception wrappers.

    graphql-core wraps exceptions that occurs on resolvers into special type
    with ``original_error`` attribute, which contains the real exception.
    """
    return err.original_error if hasattr(err, 'original_error') else err


def format_errors(errors):
    """
    Formats list of exceptions, ``errors``, into json-string.

    ``GraphQLError exceptions`` contain additional information like line and
    column number, where the exception at query resolution happened. This
    method tries to extract that information.
    """
    return json.dumps(
        [
            format_error(err) if hasattr(err, 'message') else str(err)
            for err in errors
        ],
        indent=2,
    )


def format_error_traceback(error, limit=20):
    """
    Returns ``limit`` lines of ``error``s exception traceback.
    """
    if error is None:
        return ""
    
    buffer_file = StringIO()
    traceback.print_exception(
        type(error),
        error,
        error.__traceback__,
        file=buffer_file,
        limit=limit,
    )
    return buffer_file.getvalue()


def format_errors_traceback(errors):
    """
    Concatenates traceback strings from list of exceptions in ``errors``.
    """
    return "\n\n".join([
        format_error_traceback(original_error(error))
        for error in errors if isinstance(error, Exception)
    ])


def _err_msg(error):
    return str(original_error(error))


def format_errors_msg(errors):
    """
    Formats error message as json string from list of exceptions ``errors``.
    """
    return _err_msg(errors[0]) if len(errors) == 1 else json.dumps(
        [
            _err_msg(error)
            for error in errors if isinstance(error, Exception)
        ],
        indent=2
    )


def _err_type(error):
    return type(original_error(error)).__name__


def format_errors_type(errors):
    """
    Formats error types as json string from list of exceptions ``errors``.
    """
    return _err_type(errors[0]) if len(errors) == 1 else json.dumps(
        [
            _err_type(error)
            for error in errors if isinstance(error, Exception)
        ],
        indent=2
    )


def resolve_query_res(query):
    """
    Extracts resource name from ``query`` string.
    """
    # split by '(' for queries with arguments
    # split by '{' for queries without arguments
    # rather full query than empty resource name
    return re.split('[({]', query, 1)[0].strip() or query