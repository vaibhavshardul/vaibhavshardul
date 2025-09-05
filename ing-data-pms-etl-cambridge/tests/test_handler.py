import sys
import types
import os
from unittest.mock import MagicMock

# Universal patch for missing modules
for mod_name in [
    'failSafePackage',
    'failSafePackage.fail_safe_validation',
    'EtlServices',
    'EtlServices.etl_utilities',
    'EtlServices.fpg_app_log',
    'EtlServices.common_params',
    'Notifications',
    'Notifications.email_send',
    'Notifications.notification',
    'Notifications.mysql_connection',
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
# Add dummy classes to submodules if needed
setattr(sys.modules['failSafePackage.fail_safe_validation'], 'fail_safe_cls', type('fail_safe_cls', (), {}))

class DummyCustomExceptions(Exception):
    pass
setattr(sys.modules['EtlServices.etl_utilities'], 'EtlUtilities', type('EtlUtilities', (), {'custom_exceptions': DummyCustomExceptions}))

# Patch EtlUtilities to have custom_logger and custom_exceptions attributes on both class and instance
if hasattr(sys.modules['EtlServices.etl_utilities'], 'EtlUtilities'):
    EtlUtilities = sys.modules['EtlServices.etl_utilities'].EtlUtilities
    setattr(EtlUtilities, 'custom_logger', MagicMock())
    setattr(EtlUtilities, 'custom_exceptions', DummyCustomExceptions)
    orig_init = getattr(EtlUtilities, '__init__', lambda self: None)
    def new_init(self, *a, **kw):
        orig_init(self, *a, **kw)
        self.custom_logger = MagicMock()
        self.custom_exceptions = DummyCustomExceptions
    EtlUtilities.__init__ = new_init

# Patch EtlServices.common_params for test import resolution
mock_common_params = types.ModuleType('EtlServices.common_params')
class CommonFunctions:
    def assign_request_metadata(self, event_info, request_event):
        return event_info
class CommonConstants:
    APP_STREAM = 'dummy_stream'
    APP_MODULE = 'dummy_module'
    APP_SUB_MODULE = 'dummy_submodule'
    def __init__(self, *args, **kwargs): pass
class CommonEventInfo:
    def __init__(self, *args, **kwargs): pass
class CommonParameters:
    def __init__(self, *args, **kwargs): pass
mock_common_params.CommonFunctions = CommonFunctions
mock_common_params.CommonConstants = CommonConstants
mock_common_params.CommonEventInfo = CommonEventInfo
mock_common_params.CommonParameters = CommonParameters
sys.modules['EtlServices.common_params'] = mock_common_params

# Remove sys.modules patching for EtlServices and Notifications here

# Patch required environment variables
os.environ.setdefault('credentials_secret_name', 'dummy_secret')
os.environ.setdefault('s3_target_dir', 'dummy_target')
os.environ.setdefault('s3_output_bucket', 'dummy_bucket')
os.environ.setdefault('tmp_dir', '/tmp')

import pytest
import json
from unittest.mock import MagicMock, patch

import src.handler as handler_mod

# Constants for repeated literals
RAWFILE = 'rawfile'
TENANT = 'tenant'
LOC = 'loc'
INPUTFILE = 'inputfile'
METRIC = 'metric'
IMPORT_ID = 1
BUCKET = 'bucket'
FILEOBJ = 'fileobj'
TRACE = 'trace'
SPAN = 'span'

@pytest.fixture
def event_info():
    mock = MagicMock()
    mock.trace_id = TRACE
    mock.span_id = SPAN
    mock.app_log.info = MagicMock()
    mock.app_log.error = MagicMock(return_value='error_record')
    mock.request_event = {}
    mock.metric_file_dict = {METRIC: [{}]}
    mock.extract_req_ids = ['req1']
    mock.tenant_id = TENANT
    mock.location_code = LOC
    mock.files_list = []
    mock.file_dict_list = []
    mock.file_dict = {}
    mock.raw_file_name = RAWFILE
    mock.input_file_name = INPUTFILE
    mock.output_metric = ''
    mock.entity_type = 0
    mock.import_id = IMPORT_ID
    mock.room_metric_df = MagicMock(empty=False)
    mock.upload_s3_bucket_name = BUCKET
    mock.upload_file_object = FILEOBJ
    mock.metric_type = METRIC
    # Add missing attributes for test coverage
    mock.input_file_extension = 'txt'
    mock.file_location_code = LOC
    return mock

@pytest.fixture
def sqs_record():
    return {"body": json.dumps({"foo": "bar"})}

@patch('src.handler.common_func.assign_request_metadata', return_value=MagicMock())
@patch('src.handler.iterate_each_metric')
@patch('src.handler.CambridgeLambdaHandler.extract_and_fetch_files', return_value=True)
def test_process_record_success(mock_extract, mock_iterate, mock_assign, event_info, sqs_record):
    handler = handler_mod.CambridgeLambdaHandler()
    handler.process_record(sqs_record, event_info)
    mock_assign.assert_called()
    mock_extract.assert_called()
    mock_iterate.assert_called()
    event_info.app_log.info.assert_any_call(event_info.trace_id, event_info.span_id, 'process_record',
        'Processing child request received for processing cambridge etl - {0}'.format(sqs_record))

@patch('src.handler.common_func.assign_request_metadata', return_value=MagicMock())
@patch('src.handler.iterate_each_metric')
@patch('src.handler.CambridgeLambdaHandler.extract_and_fetch_files', return_value=False)
def test_process_record_failure(mock_extract, mock_iterate, mock_assign, event_info, sqs_record):
    handler = handler_mod.CambridgeLambdaHandler()
    handler.handle_record_failure = MagicMock()
    handler.process_record(sqs_record, event_info)
    handler.handle_record_failure.assert_called()
    mock_iterate.assert_not_called()

@patch('src.handler.Utility')
@patch('src.handler.fetch_number_of_files', return_value=True)
@patch('src.handler.get_metric_file_dict', return_value=True)
def test_extract_and_fetch_files_success(mock_metric_dict, mock_fetch_files, mock_utility, event_info):
    mock_utility.return_value.extract_location_info.return_value = True
    handler = handler_mod.CambridgeLambdaHandler()
    assert handler.extract_and_fetch_files(event_info) is True
    mock_utility.return_value.extract_location_info.assert_called()
    mock_fetch_files.assert_called()
    mock_metric_dict.assert_called()

@patch('src.handler.Utility')
@patch('src.handler.fetch_number_of_files', return_value=False)
@patch('src.handler.get_metric_file_dict', return_value=True)
def test_extract_and_fetch_files_fetch_fail(mock_metric_dict, mock_fetch_files, mock_utility, event_info):
    mock_utility.return_value.extract_location_info.return_value = True
    handler = handler_mod.CambridgeLambdaHandler()
    assert handler.extract_and_fetch_files(event_info) is False

@patch('src.handler.Utility')
@patch('src.handler.fetch_number_of_files', return_value=True)
@patch('src.handler.get_metric_file_dict', return_value=False)
def test_extract_and_fetch_files_metric_dict_fail(mock_metric_dict, mock_fetch_files, mock_utility, event_info):
    mock_utility.return_value.extract_location_info.return_value = True
    handler = handler_mod.CambridgeLambdaHandler()
    assert handler.extract_and_fetch_files(event_info) is False

@patch('src.handler.Utility')
@patch('src.handler.fetch_number_of_files', return_value=True)
@patch('src.handler.get_metric_file_dict', return_value=True)
def test_extract_and_fetch_files_location_fail(mock_metric_dict, mock_fetch_files, mock_utility, event_info):
    mock_utility.return_value.extract_location_info.return_value = False
    handler = handler_mod.CambridgeLambdaHandler()
    assert handler.extract_and_fetch_files(event_info) is False

@patch('src.handler.Utility')
@patch('src.handler.fetch_number_of_files', side_effect=Exception('fail'))
def test_extract_and_fetch_files_exception(mock_fetch_files, event_info):
    handler = handler_mod.CambridgeLambdaHandler()
    with pytest.raises(Exception):
        handler.extract_and_fetch_files(event_info)

@patch('src.handler.handler_instance')
def test_lambda_handler(mock_handler):
    event = {'foo': 'bar'}
    context = MagicMock()
    handler_mod.lambda_handler(event, context)
    mock_handler.lambda_handler.assert_called_with(event, context) 

# Patch SendEmailNotification for handler tests if not present
sys.modules['src.handler'] = sys.modules.get('src.handler', types.ModuleType('src.handler'))
setattr(sys.modules['src.handler'], 'SendEmailNotification', type('DummySendEmailNotification', (), {'execute': lambda self: None})) 