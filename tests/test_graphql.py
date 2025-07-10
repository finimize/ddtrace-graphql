import json
import os

import graphql
# Try to import encoders from new location, fallback to old location
try:
    from ddtrace.internal.encoding import JSONEncoder, MsgpackEncoder
except ImportError:
    try:
        from ddtrace.encoding import JSONEncoder, MsgpackEncoder
    except ImportError:
        # If neither works, create dummy encoders for testing
        class JSONEncoder:
            def encode_traces(self, traces):
                pass
            def encode_services(self, services):
                pass
        
        class MsgpackEncoder:
            def encode_traces(self, traces):
                pass
            def encode_services(self, services):
                pass
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
# For newer ddtrace versions, use the tracer instance directly
import ddtrace

# Try to import AgentWriter from new location, fallback to old location
try:
    from ddtrace.internal.writer import AgentWriter
except ImportError:
    try:
        from ddtrace.writer import AgentWriter
    except ImportError:
        # Create dummy writer for testing
        class AgentWriter:
            def __init__(self):
                pass
from graphql import GraphQLField, GraphQLObjectType, GraphQLString
from graphql.execution import ExecutionResult
from graphql.language.parser import parse as graphql_parse
from graphql.language.source import Source as GraphQLSource
from wrapt import FunctionWrapper

import ddtrace_graphql
from ddtrace_graphql import (
    DATA_EMPTY, ERRORS, INVALID, QUERY, SERVICE, CLIENT_ERROR,
    TracedGraphQLSchema, patch, traced_graphql, unpatch
)
from ddtrace_graphql.base import traced_graphql_wrapped


class DummyWriter(AgentWriter):
    """
    # NB: This is coy fo DummyWriter class from ddtraces tests suite

    DummyWriter is a small fake writer used for tests. not thread-safe.
    """

    def __init__(self):
        # original call with agent_url for newer ddtrace versions
        try:
            super(DummyWriter, self).__init__(agent_url="http://localhost:8126")
        except TypeError:
            # Fallback for older ddtrace versions that don't require agent_url
            super(DummyWriter, self).__init__()
        # dummy components
        self.spans = []
        self.traces = []
        self.services = {}
        self.json_encoder = JSONEncoder()
        self.msgpack_encoder = MsgpackEncoder()

    def write(self, spans=None, services=None):
        if spans:
            # the traces encoding expect a list of traces so we
            # put spans in a list like we do in the real execution path
            # with both encoders
            if hasattr(self, 'json_encoder') and hasattr(self, 'msgpack_encoder'):
                trace = [spans]
                self.json_encoder.encode_traces(trace)
                self.msgpack_encoder.encode_traces(trace)
                self.spans += spans
                self.traces += trace
            else:
                # For newer ddtrace, just collect spans directly
                if isinstance(spans, list):
                    self.spans.extend(spans)
                else:
                    self.spans.append(spans)
                self.traces.append(spans)

        if services:
            if hasattr(self, 'json_encoder') and hasattr(self, 'msgpack_encoder'):
                self.json_encoder.encode_services(services)
                self.msgpack_encoder.encode_services(services)
            self.services.update(services)

    def pop(self):
        # dummy method
        s = self.spans
        self.spans = []
        return s

    def pop_traces(self):
        # dummy method
        traces = self.traces
        self.traces = []
        return traces

    def pop_services(self):
        # dummy method
        s = self.services
        self.services = {}
        return s


def get_dummy_tracer():
    # Use the global tracer instance for newer ddtrace versions
    tracer = ddtrace.tracer
    tracer.writer = DummyWriter()
    return tracer


def get_traced_schema(tracer=None, query=None, resolver=None):
    resolver = resolver or (lambda *_: 'world')
    tracer = tracer or get_dummy_tracer()
    query = query or GraphQLObjectType(
        name='RootQueryType',
        fields={
            'hello': GraphQLField(
                type_=GraphQLString,
                resolve=resolver,
            )
        }
    )
    return tracer, TracedGraphQLSchema(query=query, datadog_tracer=tracer)


class TestGraphQL:

    def test_unpatch(self):
        gql = graphql.graphql
        unpatch()
        assert gql == graphql.graphql
        assert not isinstance(graphql.graphql, FunctionWrapper)
        patch()
        assert isinstance(graphql.graphql, FunctionWrapper)

        tracer, schema = get_traced_schema()
        import asyncio
        result = graphql.graphql(schema, '{ hello }')
        if asyncio.iscoroutine(result):
            # For async results, run the coroutine
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(result)
            finally:
                loop.close()
        
        # Force the tracer to flush spans to the writer
        tracer.flush()
        span = tracer.writer.pop()[0]

        unpatch()
        assert gql == graphql.graphql

        cb_args = {}
        def test_cb(**kwargs):
            cb_args.update(kwargs)
        patch(span_callback=test_cb)
        assert isinstance(graphql.graphql, FunctionWrapper)

        result = graphql.graphql(schema, '{ hello }')
        span = tracer.writer.pop()[0]
        assert cb_args['span'] is span
        assert cb_args['result'] is result

        unpatch()
        assert gql == graphql.graphql



    def test_invalid(self):
        tracer, schema = get_traced_schema()
        result = traced_graphql(schema, '{ hello world }')
        span = tracer.writer.pop()[0]
        assert span.get_metric(INVALID) == result.invalid == 1
        assert span.get_metric(DATA_EMPTY) == 1
        assert span.error == 0

        result = traced_graphql(schema, '{ hello }')
        span = tracer.writer.pop()[0]
        assert span.get_metric(INVALID) == result.invalid == 0
        assert span.error == 0

    def test_unhandled_exception(self):

        def exc_resolver(*args):
            raise Exception('Testing stuff')

        tracer, schema = get_traced_schema(resolver=exc_resolver)
        result = traced_graphql(schema, '{ hello }')
        span = tracer.writer.pop()[0]
        assert span.get_metric(INVALID) == 0
        assert span.error == 1
        assert span.get_metric(CLIENT_ERROR) == 0
        assert span.get_metric(DATA_EMPTY) == 0

        error_stack = span.get_tag(ddtrace_errors.ERROR_STACK)
        assert 'Testing stuff' in error_stack
        assert 'Traceback' in error_stack

        error_msg = span.get_tag(ddtrace_errors.ERROR_MSG)
        assert 'Testing stuff' in error_msg

        error_type = span.get_tag(ddtrace_errors.ERROR_TYPE)
        assert 'Exception' in error_type

        try:
            raise Exception('Testing stuff')
        except Exception as exc:
            _error = exc

        def _tg(*args, **kwargs):
            def func(*args, **kwargs):
                return ExecutionResult(
                    errors=[_error],
                    invalid=True,
                )
            return traced_graphql_wrapped(func, args, kwargs)

        tracer, schema = get_traced_schema(resolver=exc_resolver)
        result = _tg(schema, '{ hello }')

        span = tracer.writer.pop()[0]
        assert span.get_metric(INVALID) == 1
        assert span.error == 1
        assert span.get_metric(DATA_EMPTY) == 1

        error_stack = span.get_tag(ddtrace_errors.ERROR_STACK)
        assert 'Testing stuff' in error_stack
        assert 'Traceback' in error_stack

    def test_not_server_error(self):
        class TestException(Exception):
            pass

        def exc_resolver(*args):
            raise TestException('Testing stuff')

        tracer, schema = get_traced_schema(resolver=exc_resolver)
        result = traced_graphql(
            schema,
            '{ hello }',
            ignore_exceptions=(TestException),
        )
        span = tracer.writer.pop()[0]
        assert span.get_metric(INVALID) == 0
        assert span.error == 0
        assert span.get_metric(DATA_EMPTY) == 0
        assert span.get_metric(CLIENT_ERROR) == 1

    def test_request_string_resolve(self):
        query = '{ hello }'

        # string as args[1]
        tracer, schema = get_traced_schema()
        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.get_tag(QUERY) == query

        # string as kwargs.get('request_string')
        tracer, schema = get_traced_schema()
        traced_graphql(schema, request_string=query)
        span = tracer.writer.pop()[0]
        assert span.get_tag(QUERY) == query

        # ast as args[1]
        tracer, schema = get_traced_schema()
        ast_query = graphql_parse(GraphQLSource(query, 'Test Request'))
        traced_graphql(schema, ast_query)
        span = tracer.writer.pop()[0]
        assert span.get_tag(QUERY) == query

        # ast as kwargs.get('request_string')
        tracer, schema = get_traced_schema()
        ast_query = graphql_parse(GraphQLSource(query, 'Test Request'))
        traced_graphql(schema, request_string=ast_query)
        span = tracer.writer.pop()[0]
        assert span.get_tag(QUERY) == query

    @staticmethod
    def test_query_tag():
        query = '{ hello }'
        tracer, schema = get_traced_schema()
        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.get_tag(QUERY) == query

        # test query also for error span, just in case
        query = '{ hello world }'
        tracer, schema = get_traced_schema()
        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.get_tag(QUERY) == query

    @staticmethod
    def test_errors_tag():
        query = '{ hello }'
        tracer, schema = get_traced_schema()
        result = traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert not span.get_tag(ERRORS)
        assert result.errors is span.get_tag(ERRORS) is None

        query = '{ hello world }'
        result = traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        span_errors = span.get_tag(ERRORS)
        assert span_errors
        _se = json.loads(span_errors)
        assert len(_se) == len(result.errors) == 1
        assert 'message' in _se[0]
        assert 'line' in _se[0]['locations'][0]
        assert 'column' in _se[0]['locations'][0]

    @staticmethod
    def test_resource():
        query = '{ hello world }'
        tracer, schema = get_traced_schema()
        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.resource == query

        query = 'mutation fnCall(args: Args) { }'
        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.resource == 'mutation fnCall'

        query = 'mutation fnCall { }'
        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.resource == 'mutation fnCall'

        query = 'mutation fnCall { }'
        traced_graphql(schema, query, span_kwargs={'resource': 'test'})
        span = tracer.writer.pop()[0]
        assert span.resource == 'test'

    @staticmethod
    def test_span_callback():
        cb_args = {}
        def test_cb(result, span):
            cb_args.update(dict(result=result, span=span))
        query = '{ hello world }'
        tracer, schema = get_traced_schema()
        result = traced_graphql(schema, query, span_callback=test_cb)
        span = tracer.writer.pop()[0]
        assert cb_args['span'] is span
        assert cb_args['result'] is result

    @staticmethod
    def test_span_kwargs_overrides():
        query = '{ hello }'
        tracer, schema = get_traced_schema()

        traced_graphql(schema, query, span_kwargs={'resource': 'test'})
        span = tracer.writer.pop()[0]
        assert span.resource == 'test'

        traced_graphql(
            schema,
            query,
            span_kwargs={
                'service': 'test',
                'name': 'test',
            }
        )
        span = tracer.writer.pop()[0]
        assert span.service == 'test'
        assert span.name == 'test'
        assert span.resource == '{ hello }'

    @staticmethod
    def test_service_from_env():
        query = '{ hello }'
        tracer, schema = get_traced_schema()

        global traced_graphql
        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.service == SERVICE

        os.environ['DDTRACE_GRAPHQL_SERVICE'] = 'test.test'

        traced_graphql(schema, query)
        span = tracer.writer.pop()[0]
        assert span.service == 'test.test'

    @staticmethod
    def test_tracer_disabled():
        query = '{ hello world }'
        tracer, schema = get_traced_schema()
        tracer.enabled = False
        traced_graphql(schema, query)
        assert not tracer.writer.pop()
