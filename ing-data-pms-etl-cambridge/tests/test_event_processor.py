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
    'product_metric',
    'product_metric.pm_transformer',
    'location_metric',
    'location_metric.lm_transformer',
    'agent_metric',
    'agent_metric.am_transformer',
    'room_metric',
    'room_metric.rm_transformer',
    'action',
    'action.event_analyzer',
    'model',
    'model.app_constants',
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

class DummyCustomExceptions(Exception):
    pass
# Add dummy classes to submodules if needed
setattr(sys.modules['failSafePackage.fail_safe_validation'], 'fail_safe_cls', type('fail_safe_cls', (), {}))
setattr(sys.modules['EtlServices.etl_utilities'], 'EtlUtilities', type('EtlUtilities', (), {'custom_exceptions': DummyCustomExceptions}))

# Add dummy transformer functions
def dummy_transformer(event_info):
    return True

setattr(sys.modules['product_metric.pm_transformer'], 'pm_transformer', dummy_transformer)
setattr(sys.modules['location_metric.lm_transformer'], 'lm_transformer', dummy_transformer)
setattr(sys.modules['agent_metric.am_transformer'], 'am_transformer', dummy_transformer)
setattr(sys.modules['room_metric.rm_transformer'], 'rm_transformer', dummy_transformer)

# Add dummy AppConstants class
class DummyAppConstants:
    DB_ING_TBL_PROCESSED_FILE_LOG = 'processed_file_log'
    DB_ING_TBL_IMPORTED_FILE_LOG = 'imported_file_log'
    MASTER_REQUEST_ID = 'master_request_id'
    EXTRACTION_PROCESSING_FAILURE = 'EXTRACTION_PROCESSING_FAILURE'
    EXTRACTION_PROCESSING_SUCCESS = 'EXTRACTION_PROCESSING_SUCCESS'
    APP_STREAM = 'dummy_stream'
    APP_MODULE = 'dummy_module'
    APP_SUB_MODULE = 'ETL_CAMBRIDGE'
    temp_dir = '/tmp'
    SOURCE_QUEUE = 'etl-cambridge-'
    DB_OPS_TBL_EXTRACT_REQUEST = 'dummy_tbl'
    EXTRACTION_PROCESSING_STARTED = 'started'
    
    def app_constant_variables(self):
        print(f"The APP_STREAM is :  {self.APP_STREAM}")
        print(f"The APP_MODULE is :  {self.APP_MODULE}")
        print(f"The APP_SUB_MODULE is :  {self.APP_SUB_MODULE}")
    
    def display_classname(self):
        print(self.__class__.__name__)
setattr(sys.modules['model.app_constants'], 'AppConstants', DummyAppConstants)

# Add dummy extract_file_info function
def dummy_extract_file_info(event_info):
    return event_info
setattr(sys.modules['action.event_analyzer'], 'extract_file_info', dummy_extract_file_info)

# Add dummy SendEmailNotification class
class DummySendEmailNotification:
    def __init__(self, record):
        self.record = record
    def execute(self):
        pass
setattr(sys.modules['Notifications.email_send'], 'SendEmailNotification', DummySendEmailNotification)

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

# Remove sys.modules patching for EtlServices and Notifications here

# Patch required environment variables
os.environ.setdefault('credentials_secret_name', 'dummy_secret')
os.environ.setdefault('s3_target_dir', 'dummy_target')
os.environ.setdefault('s3_output_bucket', 'dummy_bucket')
os.environ.setdefault('tmp_dir', '/tmp')

import pytest
from unittest.mock import patch
import src.action.event_processor as processor

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

# Patch custom_exceptions in processor to be a subclass of Exception for test context
class DummyCustomException(Exception):
    pass
processor.custom_exceptions = DummyCustomException

@pytest.fixture
def event_info():
    mock = MagicMock()
    mock.trace_id = 'trace'
    mock.span_id = 'span'
    mock.tenant_id = 'tenant'
    mock.location_code = 'loc'
    mock.metric_type = 'PM'
    mock.input_file_name = 'inputfile'
    mock.entity_type = 47
    mock.output_file_name = 'outputfile'
    mock.room_metric_df = MagicMock(empty=False)
    mock.metric_file_dict = {'PM': [{}]}
    # Ensure all required keys are present in file_dict and file_dict_list
    file_dict = {'s3_bucket_name': 'bucket', 'file_object': 'fileobj', 'req_id': 'req1', 'raw_file_name': 'rawfile', 'metric_type': 'PM'}
    mock.file_dict_list = [file_dict]
    mock.file_dict = file_dict
    mock.upload_s3_bucket_name = 'bucket'
    mock.upload_file_object = 'fileobj'
    mock.app_log.info = MagicMock()
    mock.app_log.error = MagicMock(return_value='error_record')
    # Add missing keys for test coverage
    mock.raw_file_name = 'rawfile'
    mock.input_file_extension = 'txt'
    mock.file_location_code = 'loc'
    return mock

@patch('src.action.event_processor.Utility')
@patch('src.action.event_processor.pm_transformer', return_value=True)
@patch('src.action.event_processor.lm_transformer', return_value=True)
@patch('src.action.event_processor.am_transformer', return_value=True)
@patch('src.action.event_processor.rm_transformer', return_value=True)
def test_call_transform_code_all_metrics(mock_rm, mock_am, mock_lm, mock_pm, mock_utility, event_info):
    event_info.metric_type = 'PM'
    assert processor.call_transform_code(event_info) is True
    event_info.metric_type = 'LM'
    assert processor.call_transform_code(event_info) is True
    event_info.metric_type = 'AM'
    assert processor.call_transform_code(event_info) is True
    event_info.metric_type = 'RM'
    assert processor.call_transform_code(event_info) is True
    event_info.metric_type = 'UNKNOWN'
    with pytest.raises(ValueError):
        processor.call_transform_code(event_info)

@patch('src.action.event_processor.Utility')
def test_call_transform_code_exception(mock_utility, event_info):
    mock_utility.side_effect = Exception('fail')
    event_info.metric_type = 'PM'
    # Patch pm_transformer to raise DummyCustomException to match the main code's except block
    with patch('src.action.event_processor.pm_transformer', side_effect=DummyCustomException('fail')):
        with patch('src.action.event_processor.log_and_send_email') as mock_log:
            result = processor.call_transform_code(event_info)
            assert result is False
            mock_log.assert_called()

@patch('src.action.event_processor.Utility')
def test_call_api_success(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.update_processed_file_log_table.return_value = True
    mock_utility.return_value.post_the_request_to_api.return_value = True
    event_info.entity_type = 47
    event_info.room_metric_df.empty = False
    assert processor.call_api(event_info) is True
    event_info.room_metric_df.empty = True
    assert processor.call_api(event_info) is True
    event_info.entity_type = 1
    assert processor.call_api(event_info) is True

@patch('src.action.event_processor.Utility')
def test_call_api_failure(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = None
    assert processor.call_api(event_info) is False

@patch('src.action.event_processor.Utility')
def test_call_api_exception(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.side_effect = Exception('fail')
    with patch('src.action.event_processor.log_and_send_email') as mock_log:
        with pytest.raises(Exception):
            processor.call_api(event_info)

@patch('src.action.event_processor.extract_file_info', return_value=True)
@patch('src.action.event_processor.call_transform_code', return_value=True)
@patch('src.action.event_processor.call_api', return_value=True)
@patch('src.action.event_processor.cleanup_and_update')
def test_process_files_success(mock_cleanup, mock_api, mock_transform, mock_extract, event_info):
    processor.process_files('PM', [event_info.file_dict], event_info)
    mock_extract.assert_called()
    mock_transform.assert_called()
    mock_api.assert_called()
    mock_cleanup.assert_called()

@patch('src.action.event_processor.extract_file_info', return_value=False)
def test_process_files_extract_fail(mock_extract, event_info):
    with patch('src.action.event_processor.update_extraction_status') as mock_update:
        processor.process_files('PM', [event_info.file_dict], event_info)
        mock_update.assert_called()

@patch('src.action.event_processor.extract_file_info', return_value=True)
@patch('src.action.event_processor.call_transform_code', return_value=False)
def test_process_files_transform_fail(mock_transform, mock_extract, event_info):
    with patch('src.action.event_processor.update_extraction_status') as mock_update:
        processor.process_files('PM', [event_info.file_dict], event_info)
        mock_update.assert_called()

@patch('src.action.event_processor.extract_file_info', return_value=True)
@patch('src.action.event_processor.call_transform_code', return_value=True)
@patch('src.action.event_processor.call_api', return_value=False)
def test_process_files_api_fail(mock_api, mock_transform, mock_extract, event_info):
    with patch('src.action.event_processor.update_extraction_status') as mock_update:
        processor.process_files('PM', [event_info.file_dict], event_info)
        mock_update.assert_called()

@patch('src.action.event_processor.Utility')
def test_update_extraction_status(mock_utility, event_info):
    processor.update_extraction_status(event_info, [{'req_id': 'req1'}], 'status')
    mock_utility.return_value.update_extract_request.assert_called()

@patch('src.action.event_processor.Utility')
def test_cleanup_and_update(mock_utility, event_info):
    processor.cleanup_and_update(event_info, [{'req_id': 'req1'}])
    mock_utility.return_value.delete_temp_file.assert_called()
    mock_utility.return_value.update_extract_request.assert_called()
    mock_utility.return_value.update_client_info_master.assert_called()

@patch('src.action.event_processor.Utility')
def test_iterate_each_metric(mock_utility, event_info):
    with patch('src.action.event_processor.process_files') as mock_process:
        processor.iterate_each_metric(event_info)
        mock_process.assert_called()

@patch('src.action.event_processor.Utility')
def test_iterate_each_metric_exception(mock_utility, event_info):
    with patch('src.action.event_processor.process_files', side_effect=DummyCustomException('fail')):
        with patch('src.action.event_processor.log_and_send_email') as mock_log:
            processor.iterate_each_metric(event_info)
            mock_log.assert_called()

def test_log_and_send_email(event_info):
    with patch('src.action.event_processor.SendEmailNotification') as mock_email:
        processor.log_and_send_email(event_info, 'test_action', 'test_message', Exception('test'))
        event_info.app_log.error.assert_called()
        mock_email.assert_called()

@patch('src.action.event_processor.Utility')
def test_call_api_exception_handling(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.side_effect = DummyCustomException('fail')
    with patch('src.action.event_processor.log_and_send_email') as mock_log:
        result = processor.call_api(event_info)
        assert result is False
        mock_log.assert_called()

@patch('src.action.event_processor.Utility')
def test_call_transform_code_with_unknown_metric(mock_utility, event_info):
    event_info.metric_type = 'UNKNOWN'
    with pytest.raises(ValueError):
        processor.call_transform_code(event_info)

@patch('src.action.event_processor.Utility')
def test_call_transform_code_with_pm_metric(mock_utility, event_info):
    event_info.metric_type = 'PM'
    with patch('src.action.event_processor.pm_transformer', return_value=True):
        result = processor.call_transform_code(event_info)
        assert result is True

@patch('src.action.event_processor.Utility')
def test_call_transform_code_with_lm_metric(mock_utility, event_info):
    event_info.metric_type = 'LM'
    with patch('src.action.event_processor.lm_transformer', return_value=True):
        result = processor.call_transform_code(event_info)
        assert result is True

@patch('src.action.event_processor.Utility')
def test_call_transform_code_with_am_metric(mock_utility, event_info):
    event_info.metric_type = 'AM'
    with patch('src.action.event_processor.am_transformer', return_value=True):
        result = processor.call_transform_code(event_info)
        assert result is True

@patch('src.action.event_processor.Utility')
def test_call_transform_code_with_rm_metric(mock_utility, event_info):
    event_info.metric_type = 'RM'
    with patch('src.action.event_processor.rm_transformer', return_value=True):
        result = processor.call_transform_code(event_info)
        assert result is True

@patch('src.action.event_processor.Utility')
def test_call_api_with_entity_type_47_and_empty_df(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.update_processed_file_log_table.return_value = True
    event_info.entity_type = 47
    event_info.room_metric_df.empty = True
    result = processor.call_api(event_info)
    assert result is True
    # When room_metric_df is empty, no info log is called
    event_info.app_log.info.assert_not_called()

@patch('src.action.event_processor.Utility')
def test_call_api_with_entity_type_47_and_non_empty_df(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.update_processed_file_log_table.return_value = True
    event_info.entity_type = 47
    event_info.room_metric_df.empty = False
    result = processor.call_api(event_info)
    assert result is True
    mock_utility.return_value.update_processed_file_log_table.assert_called()

@patch('src.action.event_processor.Utility')
def test_call_api_with_other_entity_type(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.post_the_request_to_api.return_value = True
    event_info.entity_type = 1
    result = processor.call_api(event_info)
    assert result is True
    mock_utility.return_value.post_the_request_to_api.assert_called()

@patch('src.action.event_processor.Utility')
def test_call_api_with_other_entity_type_failure(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.post_the_request_to_api.return_value = False
    event_info.entity_type = 1
    result = processor.call_api(event_info)
    assert result is False

@patch('src.action.event_processor.Utility')
def test_call_api_with_other_entity_type_exception(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.post_the_request_to_api.side_effect = DummyCustomException('fail')
    event_info.entity_type = 1
    with patch('src.action.event_processor.log_and_send_email') as mock_log:
        result = processor.call_api(event_info)
        assert result is False
        mock_log.assert_called()

def test_process_files_with_single_file(event_info):
    event_info.metric_file_dict = {'PM': [{'s3_bucket_name': 'bucket', 'file_object': 'fileobj'}]}
    with patch('src.action.event_processor.extract_file_info', return_value=True) as mock_extract:
        with patch('src.action.event_processor.call_transform_code', return_value=True) as mock_transform:
            with patch('src.action.event_processor.call_api', return_value=True) as mock_api:
                with patch('src.action.event_processor.cleanup_and_update') as mock_cleanup:
                    processor.process_files('PM', [{'s3_bucket_name': 'bucket', 'file_object': 'fileobj'}], event_info)
                    mock_extract.assert_called()
                    mock_transform.assert_called()
                    mock_api.assert_called()
                    mock_cleanup.assert_called()

def test_process_files_with_multiple_files(event_info):
    files_list = [
        {'s3_bucket_name': 'bucket1', 'file_object': 'fileobj1'},
        {'s3_bucket_name': 'bucket2', 'file_object': 'fileobj2'}
    ]
    with patch('src.action.event_processor.extract_file_info', return_value=True) as mock_extract:
        with patch('src.action.event_processor.call_transform_code', return_value=True) as mock_transform:
            with patch('src.action.event_processor.call_api', return_value=True) as mock_api:
                with patch('src.action.event_processor.cleanup_and_update') as mock_cleanup:
                    processor.process_files('PM', files_list, event_info)
                    # Should use the last file in the list
                    assert event_info.upload_s3_bucket_name == 'bucket2'
                    assert event_info.upload_file_object == 'fileobj2'
                    mock_cleanup.assert_called()

@patch('src.action.event_processor.Utility')
def test_update_extraction_status_with_multiple_files(mock_utility, event_info):
    files_list = [
        {'req_id': 'req1'},
        {'req_id': 'req2'},
        {'req_id': 'req3'}
    ]
    processor.update_extraction_status(event_info, files_list, 'FAILED')
    assert mock_utility.return_value.update_extract_request.call_count == 3

@patch('src.action.event_processor.Utility')
def test_cleanup_and_update_with_multiple_files(mock_utility, event_info):
    files_list = [
        {'req_id': 'req1'},
        {'req_id': 'req2'}
    ]
    processor.cleanup_and_update(event_info, files_list)
    mock_utility.return_value.delete_temp_file.assert_called_once()
    assert mock_utility.return_value.update_extract_request.call_count == 2
    mock_utility.return_value.update_client_info_master.assert_called_once()

@patch('src.action.event_processor.Utility')
def test_cleanup_and_update_with_empty_files_list(mock_utility, event_info):
    processor.cleanup_and_update(event_info, [])
    mock_utility.return_value.delete_temp_file.assert_called_once()
    mock_utility.return_value.update_client_info_master.assert_called_once()

def test_event_info_fixture_attributes(event_info):
    """Test that the event_info fixture has all required attributes"""
    assert event_info.trace_id == 'trace'
    assert event_info.span_id == 'span'
    assert event_info.tenant_id == 'tenant'
    assert event_info.location_code == 'loc'
    assert event_info.metric_type == 'PM'
    assert event_info.input_file_name == 'inputfile'
    assert event_info.entity_type == 47
    assert event_info.output_file_name == 'outputfile'
    assert event_info.room_metric_df.empty is False
    assert event_info.raw_file_name == 'rawfile'
    assert event_info.input_file_extension == 'txt'
    assert event_info.file_location_code == 'loc'

# Additional tests for better coverage
@patch('src.action.event_processor.Utility')
def test_call_api_with_entity_type_47_and_non_empty_df_logs_info(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.update_processed_file_log_table.return_value = True
    event_info.entity_type = 47
    event_info.room_metric_df.empty = False
    result = processor.call_api(event_info)
    assert result is True
    # Should log info when room_metric_df is not empty
    event_info.app_log.info.assert_called()

@patch('src.action.event_processor.Utility')
def test_call_api_with_entity_type_47_and_empty_df_no_log(mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    event_info.entity_type = 47
    event_info.room_metric_df.empty = True
    result = processor.call_api(event_info)
    assert result is True
    # Should not log info when room_metric_df is empty
    event_info.app_log.info.assert_not_called()

def test_process_files_sets_correct_attributes(event_info):
    files_list = [
        {'s3_bucket_name': 'bucket1', 'file_object': 'fileobj1'},
        {'s3_bucket_name': 'bucket2', 'file_object': 'fileobj2'}
    ]
    with patch('src.action.event_processor.extract_file_info', return_value=True):
        with patch('src.action.event_processor.call_transform_code', return_value=True):
            with patch('src.action.event_processor.call_api', return_value=True):
                with patch('src.action.event_processor.cleanup_and_update'):
                    processor.process_files('PM', files_list, event_info)
                    # Should set metric_type
                    assert event_info.metric_type == 'PM'
                    # Should set file_dict_list
                    assert event_info.file_dict_list == files_list
                    # Should set file_dict to last file
                    assert event_info.file_dict == files_list[-1]
                    # Should set upload attributes from last file
                    assert event_info.upload_s3_bucket_name == 'bucket2'
                    assert event_info.upload_file_object == 'fileobj2'

@patch('src.action.event_processor.Utility')
def test_update_extraction_status_calls_utility_for_each_file(mock_utility, event_info):
    files_list = [
        {'req_id': 'req1'},
        {'req_id': 'req2'},
        {'req_id': 'req3'}
    ]
    processor.update_extraction_status(event_info, files_list, 'FAILED')
    # Should call update_extract_request for each file
    assert mock_utility.return_value.update_extract_request.call_count == 3
    # Check that it was called with correct arguments
    mock_utility.return_value.update_extract_request.assert_any_call(event_info, 'req1', 'FAILED')
    mock_utility.return_value.update_extract_request.assert_any_call(event_info, 'req2', 'FAILED')
    mock_utility.return_value.update_extract_request.assert_any_call(event_info, 'req3', 'FAILED')

@patch('src.action.event_processor.Utility')
def test_cleanup_and_update_calls_all_required_methods(mock_utility, event_info):
    files_list = [
        {'req_id': 'req1'},
        {'req_id': 'req2'}
    ]
    processor.cleanup_and_update(event_info, files_list)
    # Should call delete_temp_file once
    mock_utility.return_value.delete_temp_file.assert_called_once_with(event_info)
    # Should call update_extract_request for each file with success status
    assert mock_utility.return_value.update_extract_request.call_count == 2
    mock_utility.return_value.update_extract_request.assert_any_call(event_info, 'req1', 'EXTRACTION_PROCESSING_SUCCESS')
    mock_utility.return_value.update_extract_request.assert_any_call(event_info, 'req2', 'EXTRACTION_PROCESSING_SUCCESS')
    # Should call update_client_info_master once
    mock_utility.return_value.update_client_info_master.assert_called_once_with(event_info)

def test_iterate_each_metric_logs_info_for_each_metric(event_info):
    event_info.metric_file_dict = {
        'PM': [{'req_id': 'req1'}],
        'LM': [{'req_id': 'req2'}],
        'AM': [{'req_id': 'req3'}]
    }
    with patch('src.action.event_processor.process_files') as mock_process:
        processor.iterate_each_metric(event_info)
        # Should call process_files for each metric
        assert mock_process.call_count == 3
        # Should log info for each metric
        assert event_info.app_log.info.call_count == 3

@patch('src.action.event_processor.Utility')
def test_call_transform_code_logs_start_message(mock_utility, event_info):
    event_info.metric_type = 'PM'
    with patch('src.action.event_processor.pm_transformer', return_value=True):
        processor.call_transform_code(event_info)
        # Should log the start message
        event_info.app_log.info.assert_called()
        # Check that the log message contains the expected content
        call_args = event_info.app_log.info.call_args[0]
        assert call_args[2] == 'call_transform_code'  # action parameter
        assert 'Calling' in call_args[3]  # message parameter
        assert 'PM' in call_args[3]  # message parameter
        assert 'tenant' in call_args[3]  # message parameter
        assert 'loc' in call_args[3]  # message parameter

@patch('src.action.event_processor.Utility')
def test_call_transform_code_with_unknown_metric_raises_value_error_with_message(mock_utility, event_info):
    event_info.metric_type = 'UNKNOWN'
    with pytest.raises(ValueError) as exc_info:
        processor.call_transform_code(event_info)
    # Check that the error message contains the expected content
    assert 'Unsupported' in str(exc_info.value)
    assert 'UNKNOWN' in str(exc_info.value)
    assert 'tenant' in str(exc_info.value)
    assert 'loc' in str(exc_info.value) 