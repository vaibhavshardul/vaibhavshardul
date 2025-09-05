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

class DummyCustomExceptions(Exception):
    pass
# Add dummy classes to submodules if needed
setattr(sys.modules['failSafePackage.fail_safe_validation'], 'fail_safe_cls', type('fail_safe_cls', (), {}))
setattr(sys.modules['EtlServices.etl_utilities'], 'EtlUtilities', type('EtlUtilities', (), {'custom_exceptions': DummyCustomExceptions}))
# Patch EtlServices.common_params for import resolution
mock_common_params = types.ModuleType('EtlServices.common_params')
class CommonFunctions:
    pass
class CommonParameters:
    pass
class CommonEventInfo:
    pass
mock_common_params.CommonFunctions = CommonFunctions
mock_common_params.CommonParameters = CommonParameters
mock_common_params.CommonEventInfo = CommonEventInfo
sys.modules['EtlServices.common_params'] = mock_common_params

# Patch required environment variables
os.environ.setdefault('credentials_secret_name', 'dummy_secret')
os.environ.setdefault('s3_target_dir', 'dummy_target')
os.environ.setdefault('s3_output_bucket', 'dummy_bucket')
os.environ.setdefault('tmp_dir', '/tmp')

import pytest
from unittest.mock import patch
import src.action.event_analyzer as analyzer

# Constants for repeated literals
RAWFILE = 'rawfile'
TENANT = 'tenant'
LOC = 'loc'
INPUTFILE = 'inputfile'
METRIC_TYPE = 'RM'
IMPORT_ID = 1
TSA03 = 'TSA03'
TSA01 = 'TSA01'
TSA04 = 'TSA04'
PM = 'PM'

# Patch Constants used in event_analyzer
class DummyConstants:
    DB_OPS_TBL_EXTRACT_REQUEST = 'dummy_tbl'
    EXTRACTION_PROCESSING_STARTED = 'started'
sys.modules['src.action.event_analyzer'].Constants = DummyConstants

@pytest.fixture
def event_info():
    mock = MagicMock()
    mock.trace_id = 'trace'
    mock.span_id = 'span'
    mock.tenant_id = TENANT
    mock.location_code = LOC
    mock.extract_req_ids = ['req1']
    mock.app_log.info = MagicMock()
    mock.app_log.error = MagicMock(return_value='error_record')
    mock.files_list = []
    mock.metric_file_dict = {}
    mock.file_dict = {'file_object': f'path/to/file~{LOC}~metric~01012020~{TSA03}.txt', 'raw_file_name': RAWFILE, 'file_type': TSA03, 'metric_type': METRIC_TYPE}
    mock.input_file_extension = 'txt'
    mock.file_location_code = LOC
    mock.metric_type = METRIC_TYPE
    mock.input_file_name = INPUTFILE
    mock.app_log.input_file_name = INPUTFILE
    mock.app_log.raw_file_name = RAWFILE
    return mock

@patch('src.action.event_analyzer.Utility')
@patch('src.action.event_analyzer.ops_db_mongo')
@patch('src.action.event_analyzer.json_util')
def test_fetch_number_of_files_success(mock_json_util, mock_ops_db, mock_utility, event_info):
    mock_ops_db.find_one.return_value = {'req_original_event_obj': {'source_file_complete_path': f's3://bucket/path/to/file~{LOC}~metric~01012020~{TSA03}.txt'}, 'file_bucket': 'bucket', 'file_path': 'path/', 'file_name': f'file~{LOC}~metric~01012020~{TSA03}.txt'}
    mock_json_util.loads.return_value = mock_ops_db.find_one.return_value
    mock_json_util.dumps.side_effect = lambda x: str(x)
    assert analyzer.fetch_number_of_files(event_info) is True
    assert event_info.files_list

@patch('src.action.event_analyzer.Utility')
@patch('src.action.event_analyzer.ops_db_mongo')
@patch('src.action.event_analyzer.json_util')
def test_fetch_number_of_files_file_info_none(mock_json_util, mock_ops_db, mock_utility, event_info):
    mock_ops_db.find_one.return_value = None
    mock_json_util.loads.return_value = None
    mock_json_util.dumps.side_effect = lambda x: str(x)
    with pytest.raises(ValueError):
        analyzer.fetch_number_of_files(event_info)

@patch('src.action.event_analyzer.Utility')
@patch('src.action.event_analyzer.ops_db_mongo')
@patch('src.action.event_analyzer.json_util')
def test_fetch_number_of_files_location_mismatch(mock_json_util, mock_ops_db, mock_utility, event_info):
    file_info = {'req_original_event_obj': {'source_file_complete_path': f's3://bucket/path/to/file~otherloc~metric~01012020~{TSA03}.txt'}, 'file_bucket': 'bucket', 'file_path': 'path/', 'file_name': f'file~otherloc~metric~01012020~{TSA03}.txt'}
    mock_ops_db.find_one.return_value = file_info
    mock_json_util.loads.return_value = file_info
    mock_json_util.dumps.side_effect = lambda x: str(x)
    with pytest.raises(ValueError):
        analyzer.fetch_number_of_files(event_info)

@patch('src.action.event_analyzer.Utility')
def test_get_metric_file_dict_success(mock_utility, event_info):
    event_info.files_list = [
        {'file_type': TSA03, 'metric_type': METRIC_TYPE},
        {'file_type': TSA01, 'metric_type': PM}
    ]
    assert analyzer.get_metric_file_dict(event_info) is True
    assert METRIC_TYPE in event_info.metric_file_dict
    assert PM in event_info.metric_file_dict

@patch('src.action.event_analyzer.Utility')
def test_get_metric_file_dict_exception(mock_utility, event_info):
    event_info.files_list = None
    event_info.metric_file_dict = {}
    with pytest.raises(TypeError):
        analyzer.get_metric_file_dict(event_info)

@patch('src.action.event_analyzer.Utility')
def test_extract_file_info_success(mock_utility, event_info):
    event_info.file_dict = {'file_object': f'path/to/file~{LOC}~metric~01012020~{TSA03}.txt', 'raw_file_name': RAWFILE}
    assert analyzer.extract_file_info(METRIC_TYPE, event_info) is True
    assert event_info.input_file_name

@patch('src.action.event_analyzer.Utility')
def test_extract_file_info_exception(mock_utility, event_info):
    event_info.file_dict = None
    event_info.input_file_name = None
    with pytest.raises(TypeError):
        analyzer.extract_file_info(METRIC_TYPE, event_info)

def test_log_and_send_email(event_info):
    with patch('src.action.event_analyzer.SendEmailNotification') as mock_email:
        analyzer.log_and_send_email(event_info, 'test_action', 'test_message', Exception('test'))
        event_info.app_log.error.assert_called()
        mock_email.assert_called()

def test_log_info(event_info):
    analyzer.log_info(event_info, 'test_action', 'test_message')
    event_info.app_log.info.assert_called_with('trace', 'span', 'test_action', 'test_message')

@patch('src.action.event_analyzer.Utility')
@patch('src.action.event_analyzer.ops_db_mongo')
@patch('src.action.event_analyzer.json_util')
def test_fetch_number_of_files_multiple_requests(mock_json_util, mock_ops_db, mock_utility, event_info):
    event_info.extract_req_ids = ['req1', 'req2']
    file_info_1 = {'req_original_event_obj': {'source_file_complete_path': f's3://bucket/path/to/file~{LOC}~metric~01012020~{TSA03}.txt'}, 'file_bucket': 'bucket', 'file_path': 'path/', 'file_name': f'file~{LOC}~metric~01012020~{TSA03}.txt'}
    file_info_2 = {'req_original_event_obj': {'source_file_complete_path': f's3://bucket/path/to/file~{LOC}~metric~01012020~{TSA04}.txt'}, 'file_bucket': 'bucket', 'file_path': 'path/', 'file_name': f'file~{LOC}~metric~01012020~{TSA04}.txt'}
    
    mock_ops_db.find_one.side_effect = [file_info_1, file_info_2]
    mock_json_util.loads.side_effect = [file_info_1, file_info_2]
    mock_json_util.dumps.side_effect = lambda x: str(x)
    result = analyzer.fetch_number_of_files(event_info)
    assert result is True
    assert len(event_info.files_list) == 2

@patch('src.action.event_analyzer.Utility')
@patch('src.action.event_analyzer.ops_db_mongo')
@patch('src.action.event_analyzer.json_util')
def test_fetch_number_of_files_exception_handling(mock_json_util, mock_ops_db, mock_utility, event_info):
    mock_ops_db.find_one.side_effect = Exception('Database error')
    mock_json_util.loads.return_value = None
    mock_json_util.dumps.side_effect = lambda x: str(x)
    with pytest.raises(Exception):
        analyzer.fetch_number_of_files(event_info) 