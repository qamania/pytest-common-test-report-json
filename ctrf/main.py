from pytest import Config, Parser, FixtureRequest, fixture
from ctrf.CommonTestReportPlugin import CTRF
from ctrf.BaseMetadataReport import BaseMetadataReport


def pytest_addoption(parser: Parser):
    group = parser.getgroup('ctrf', 'generate test report in CTR format')
    group.addoption('--ctrf',
                    action='store',
                    help='generate test report. Report file name is optional')


def pytest_configure(config: Config):
    if not config.option.ctrf:
        return
    if hasattr(config, 'workerinput'):
        plugin = BaseMetadataReport()
    else:
        plugin = CTRF()
    setattr(config, '_ctrf', plugin)
    config.pluginmanager.register(plugin, name='ctrf_plugin')
    pass


def pytest_unconfigure(config: Config):
    ctrf = getattr(config, '_ctrf', None)
    if ctrf is not None:
        delattr(config, '_ctrf')
    if config.pluginmanager.hasplugin('ctrf_plugin'):
        config.pluginmanager.unregister(name='ctrf_plugin')


@fixture(autouse=True)
def ctrf_json_metadata(request: FixtureRequest):
    if not request.config.option.ctrf:
        return
    tags = list()
    for mark in request.node.iter_markers():
        tag = mark.name
        if tag == 'parametrize':
            continue
        if mark.args:
            for arg in mark.args:
                tag += f'::{arg}'
        if mark.kwargs:
            for key, value in mark.kwargs.items():
                tag += f'::{key}_{value}'
        tags.append(tag)
    request.node._ctrf_metadata.setdefault('tags', tags)
    if hasattr(request.node, 'callspec'):
        params = request.node.callspec.params
        browser = params.get('browser_name')
        if browser:
            request.node._ctrf_metadata.setdefault('browser', browser)
        request.node._ctrf_metadata.setdefault(
            'parameters', {key: _serializable_param(value) for key, value in params.items()})
    return request.node._ctrf_metadata


MAX_PARAM_LENGTH = 200


def _serializable_param(value):
    # keep only primitives: report metadata is sent between xdist workers and dumped to json;
    # long values are truncated to keep the report small (see issue 6)
    if not isinstance(value, (str, int, float, bool, type(None))):
        value = repr(value)
    if isinstance(value, str) and len(value) > MAX_PARAM_LENGTH:
        value = value[:MAX_PARAM_LENGTH] + '...'
    return value
