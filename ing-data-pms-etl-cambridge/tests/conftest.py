import sys
import os
import types
import pytest
from unittest.mock import MagicMock

# Prepend the test directory to sys.path for import resolution
sys.path.insert(0, os.path.dirname(__file__))

# Patch EtlServices and Notifications as packages
EtlServices = types.ModuleType('EtlServices')
EtlServices.__path__ = []
Notifications = types.ModuleType('Notifications')
Notifications.__path__ = []
sys.modules['EtlServices'] = EtlServices
sys.modules['Notifications'] = Notifications

# Patch EtlServices submodules
sys.modules['EtlServices.etl_utilities'] = types.ModuleType('EtlServices.etl_utilities')
sys.modules['EtlServices.fpg_app_log'] = types.ModuleType('EtlServices.fpg_app_log')
sys.modules['EtlServices.common_params'] = types.ModuleType('EtlServices.common_params')
sys.modules['EtlServices.fpg_ing_mysql'] = types.ModuleType('EtlServices.fpg_ing_mysql')
sys.modules['EtlServices.fpg_ops_mongo'] = types.ModuleType('EtlServices.fpg_ops_mongo')
sys.modules['EtlServices.gnupg'] = types.ModuleType('EtlServices.gnupg')
sys.modules['EtlServices.base_lambda_handler'] = types.ModuleType('EtlServices.base_lambda_handler')

# Patch Notifications submodules
sys.modules['Notifications.email_send'] = types.ModuleType('Notifications.email_send')
sys.modules['Notifications.notification'] = types.ModuleType('Notifications.notification')
sys.modules['Notifications.mysql_connection'] = types.ModuleType('Notifications.mysql_connection')

# Preload pandas and numpy shims at import time so src modules can import them
import mock_pandas
import mock_numpy
sys.modules['pandas'] = mock_pandas
sys.modules['numpy'] = mock_numpy

# Provide pandasql shim
if 'pandasql' not in sys.modules:
    pandasql_mod = types.ModuleType('pandasql')
    def _dummy_sqldf(*args, **kwargs):
        return MagicMock()
    setattr(pandasql_mod, 'sqldf', _dummy_sqldf)
    sys.modules['pandasql'] = pandasql_mod

# Provide a boto3 shim before any src imports that require it
if 'boto3' not in sys.modules:
    boto3_mod = types.ModuleType('boto3')
    setattr(boto3_mod, 'client', lambda *a, **k: MagicMock())
    sys.modules['boto3'] = boto3_mod

# Provide bson shim for MongoDB utilities
if 'bson' not in sys.modules:
    bson_mod = types.ModuleType('bson')
    json_util_mod = types.ModuleType('bson.json_util')
    def _dummy_loads(*args, **kwargs):
        return args[0] if args else None
    def _dummy_dumps(*args, **kwargs):
        return str(args[0]) if args else '{}'
    setattr(json_util_mod, 'loads', _dummy_loads)
    setattr(json_util_mod, 'dumps', _dummy_dumps)
    setattr(bson_mod, 'json_util', json_util_mod)
    sys.modules['bson'] = bson_mod
    sys.modules['bson.json_util'] = json_util_mod

# Add dummy classes to EtlServices submodules
class DummyEtlUtilities:
    custom_exceptions = type('custom_exceptions', (), {})()
    def __init__(self, *args, **kwargs): pass
    def __call__(self, *args, **kwargs): return self
setattr(sys.modules['EtlServices.etl_utilities'], 'EtlUtilities', DummyEtlUtilities)

class DummyFpgAppLog:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.fpg_app_log'], 'FpgAppLog', DummyFpgAppLog)

class DummyFpgIngMySQL:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.fpg_ing_mysql'], 'FpgIngMySQL', DummyFpgIngMySQL)

class DummyFpgOpsMongo:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.fpg_ops_mongo'], 'FpgOpsMongo', DummyFpgOpsMongo)

class DummyCommonConstants:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.common_params'], 'CommonConstants', DummyCommonConstants)

class DummyCommonEventInfo:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.common_params'], 'CommonEventInfo', DummyCommonEventInfo)

class DummyCommonParameters:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.common_params'], 'CommonParameters', DummyCommonParameters)

class DummyCommonFunctions:
    def assign_request_metadata(self, *args, **kwargs):
        return args[0] if args else None
setattr(sys.modules['EtlServices.common_params'], 'CommonFunctions', DummyCommonFunctions)
sys.modules['EtlServices.common_params'].__dict__['CommonFunctions'] = DummyCommonFunctions

class DummyGnupg:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.gnupg'], 'gnupg', DummyGnupg)

class DummyBaseLambdaHandler:
    def __init__(self, *args, **kwargs): pass
setattr(sys.modules['EtlServices.base_lambda_handler'], 'BaseLambdaHandler', DummyBaseLambdaHandler)

# Add dummy SendEmailNotification to Notifications.email_send
class DummySendEmailNotification:
    def __init__(self, *args, **kwargs): pass
    def execute(self, *args, **kwargs): return True
setattr(sys.modules['Notifications.email_send'], 'SendEmailNotification', DummySendEmailNotification)

# Patch src.model.app_constants.AppConstants for tests
sys.modules['src.model.app_constants'] = types.ModuleType('src.model.app_constants')
class DummyAppConstants(object):
    MASTER_REQUEST_ID = 'dummy_master_request_id'
    DB_ING_TBL_IMPORTED_FILE_LOG = 'dummy_imported_file_log'
    DB_ING_TBL_PROCESSED_FILE_LOG = 'dummy_processed_file_log'
    EXTRACTION_PROCESSING_SUCCESS = 'dummy_success'
    EXTRACTION_PROCESSING_FAILURE = 'dummy_failure'
    EXTRACTION_PROCESSING_STARTED = 'dummy_started'
    # Add any other constants as needed for tests
sys.modules['src.model.app_constants'].AppConstants = DummyAppConstants
sys.modules['src.model.app_constants'].Constants = DummyAppConstants

# Fix custom_exceptions to inherit from Exception
class DummyCustomExceptions(Exception):
    pass
DummyEtlUtilities.custom_exceptions = DummyCustomExceptions

# Create alias/stub package 'action' for absolute imports in src modules
action_pkg = types.ModuleType('action')
action_pkg.__path__ = []
sys.modules['action'] = action_pkg

# Provide stub implementations sufficient for imports; tests will patch as needed
event_analyzer_stub = types.ModuleType('action.event_analyzer')
def _stub_get_tsa06_df(df, event_info):
    return df
def _stub_check_original_file_name(event_info, prefix):
    return getattr(event_info, 'raw_file_name', 'rawfile')
def _stub_get_rm_df(df, event_info):
    return df
def _stub_get_tsa03_df(df, event_info):
    return df
def _stub_get_tsa04_df(df, event_info):
    return df
def _stub_get_tsa05_df(df, event_info):
    return df
def _stub_get_tsa01_df(df, event_info):
    return df
def _stub_get_tsa02_df(df, event_info):
    return df
def _stub_fetch_number_of_files(event_info):
    return True
def _stub_get_metric_file_dict(event_info):
    return True
def _stub_extract_file_info(metric_type, event_info):
    return True
setattr(event_analyzer_stub, 'get_tsa06_df', _stub_get_tsa06_df)
setattr(event_analyzer_stub, 'check_original_file_name', _stub_check_original_file_name)
setattr(event_analyzer_stub, 'get_rm_df', _stub_get_rm_df)
setattr(event_analyzer_stub, 'get_tsa03_df', _stub_get_tsa03_df)
setattr(event_analyzer_stub, 'get_tsa04_df', _stub_get_tsa04_df)
setattr(event_analyzer_stub, 'get_tsa05_df', _stub_get_tsa05_df)
setattr(event_analyzer_stub, 'get_tsa01_df', _stub_get_tsa01_df)
setattr(event_analyzer_stub, 'get_tsa02_df', _stub_get_tsa02_df)
setattr(event_analyzer_stub, 'fetch_number_of_files', _stub_fetch_number_of_files)
setattr(event_analyzer_stub, 'get_metric_file_dict', _stub_get_metric_file_dict)
setattr(event_analyzer_stub, 'extract_file_info', _stub_extract_file_info)
sys.modules['action.event_analyzer'] = event_analyzer_stub

event_processor_stub = types.ModuleType('action.event_processor')
def _stub_iterate_each_metric(event_info):
    return True
setattr(event_processor_stub, 'iterate_each_metric', _stub_iterate_each_metric)
sys.modules['action.event_processor'] = event_processor_stub

# Create model package and app_constants stub
model_pkg = types.ModuleType('model')
model_pkg.__path__ = []
sys.modules['model'] = model_pkg

app_constants_stub = types.ModuleType('model.app_constants')
class DummyAppConstants:
    DB_ING_TBL_IMPORTED_FILE_LOG = 'dummy_imported_file_log'
    DB_ING_TBL_PROCESSED_FILE_LOG = 'dummy_processed_file_log'
    EXTRACTION_PROCESSING_SUCCESS = 'dummy_success'
    EXTRACTION_PROCESSING_FAILURE = 'dummy_failure'
    EXTRACTION_PROCESSING_STARTED = 'dummy_started'
    DB_OPS_TBL_EXTRACT_REQUEST = 'dummy_tbl'
    MASTER_REQUEST_ID = 'dummy_master_request_id'
setattr(app_constants_stub, 'AppConstants', DummyAppConstants)
sys.modules['model.app_constants'] = app_constants_stub

# Create model.event_info stub
event_info_stub = types.ModuleType('model.event_info')
class DummyEventInfo:
    def __init__(self, *args, **kwargs):
        pass
setattr(event_info_stub, 'EventInfo', DummyEventInfo)
sys.modules['model.event_info'] = event_info_stub

# Create agent_metric package stub for relative imports
agent_metric_pkg = types.ModuleType('agent_metric')
agent_metric_pkg.__path__ = []
sys.modules['agent_metric'] = agent_metric_pkg

am_transformer_stub = types.ModuleType('agent_metric.am_transformer')
def _stub_am_transformer(event_info):
    return True
setattr(am_transformer_stub, 'am_transformer', _stub_am_transformer)
sys.modules['agent_metric.am_transformer'] = am_transformer_stub

# Create location_metric package stub for relative imports
location_metric_pkg = types.ModuleType('location_metric')
location_metric_pkg.__path__ = []
sys.modules['location_metric'] = location_metric_pkg

lm_transformer_stub = types.ModuleType('location_metric.lm_transformer')
def _stub_lm_transformer(event_info):
    return True
setattr(lm_transformer_stub, 'lm_transformer', _stub_lm_transformer)
sys.modules['location_metric.lm_transformer'] = lm_transformer_stub

@pytest.fixture(autouse=True)
def patch_pandas_and_numpy(monkeypatch):
    # Already preloaded globally; ensure they stay present during tests
    monkeypatch.setitem(sys.modules, 'pandas', sys.modules['pandas'])
    monkeypatch.setitem(sys.modules, 'numpy', sys.modules['numpy'])
    yield