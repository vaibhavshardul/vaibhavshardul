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
    'action',
    'action.event_analyzer',
    'model',
    'model.app_constants',
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# Add dummy classes to submodules if needed
setattr(sys.modules['failSafePackage.fail_safe_validation'], 'fail_safe_cls', type('fail_safe_cls', (), {}))

class DummyCustomExceptions(Exception):
    pass
setattr(sys.modules['EtlServices.etl_utilities'], 'EtlUtilities', type('EtlUtilities', (), {'custom_exceptions': DummyCustomExceptions}))

# Add dummy AppConstants class for transformer tests
class DummyAppConstants:
    DB_ING_TBL_IMPORTED_FILE_LOG = 'imported_file_log'
setattr(sys.modules['model.app_constants'], 'AppConstants', DummyAppConstants)

# Add dummy functions for action.event_analyzer
def dummy_get_rm_df(df, event_info):
    return df
def dummy_check_original_file_name(event_info, metric_type):
    return 'rawfile'
setattr(sys.modules['action.event_analyzer'], 'get_rm_df', dummy_get_rm_df)
setattr(sys.modules['action.event_analyzer'], 'check_original_file_name', dummy_check_original_file_name)

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

# Patch required environment variables
os.environ.setdefault('credentials_secret_name', 'dummy_secret')
os.environ.setdefault('s3_target_dir', 'dummy_target')
os.environ.setdefault('s3_output_bucket', 'dummy_bucket')
os.environ.setdefault('tmp_dir', '/tmp')

import pytest
from unittest.mock import patch, call, MagicMock
import src.room_metric.rm_transformer as rm_mod

# Constants for repeated literals
RAWFILE = 'rawfile'
TENANT = 'tenant'
LOC = 'loc'
INPUTFILE = 'inputfile'
METRIC_TYPE = 'RM'
IMPORT_ID = 1
TSA03 = 'TSA03'

@pytest.fixture
def event_info():
    mock = MagicMock()
    mock.trace_id = 'trace'
    mock.span_id = 'span'
    mock.tenant_id = TENANT
    mock.location_code = LOC
    mock.metric_type = METRIC_TYPE
    mock.input_file_name = INPUTFILE
    mock.app_log.info = MagicMock()
    mock.app_log.error = MagicMock(return_value='error_record')
    mock.file_dict_list = [{'file_type': TSA03}]
    mock.room_metric_df = MagicMock()
    mock.import_id = IMPORT_ID
    return mock

# ========== rm_transformer function tests ==========

@patch('src.room_metric.rm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.room_metric.rm_transformer.Utility')
@patch('src.room_metric.rm_transformer.process_rm', return_value=MagicMock(empty=False))
def test_rm_transformer_success_upload_true(mock_process_rm, mock_utility, mock_check, event_info):
    """Test successful transformation with upload_file_s3 returning True"""
    mock_utility.return_value.insert_log_table.return_value = IMPORT_ID
    mock_utility.return_value.upload_file_s3.return_value = True
    
    result = rm_mod.rm_transformer(event_info)
    
    assert result is True
    assert event_info.output_metric == "ROOM_METRIC"
    assert event_info.entity_type == 47
    assert event_info.raw_file_name == 'rawfile'
    mock_check.assert_called_once_with(event_info, "RM")
    mock_utility.return_value.insert_log_table.assert_called_once()
    mock_process_rm.assert_called_once_with(event_info)
    mock_utility.return_value.upload_file_s3.assert_called_once()

@patch('src.room_metric.rm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.room_metric.rm_transformer.Utility')
@patch('src.room_metric.rm_transformer.process_rm', return_value=MagicMock(empty=False))
def test_rm_transformer_success_upload_false(mock_process_rm, mock_utility, mock_check, event_info):
    """Test successful transformation with upload_file_s3 returning False"""
    mock_utility.return_value.insert_log_table.return_value = IMPORT_ID
    mock_utility.return_value.upload_file_s3.return_value = False
    
    result = rm_mod.rm_transformer(event_info)
    
    assert result is False
    mock_utility.return_value.upload_file_s3.assert_called_once()

@patch('src.room_metric.rm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.room_metric.rm_transformer.Utility')
def test_rm_transformer_import_id_none(mock_utility, mock_check, event_info):
    """Test when insert_log_table returns None"""
    mock_utility.return_value.insert_log_table.return_value = None
    
    result = rm_mod.rm_transformer(event_info)
    
    assert result is False
    mock_utility.return_value.insert_log_table.assert_called_once()

@patch('src.room_metric.rm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.room_metric.rm_transformer.Utility')
@patch('src.room_metric.rm_transformer.process_rm', return_value=None)
def test_rm_transformer_process_rm_none(mock_process_rm, mock_utility, mock_check, event_info):
    """Test when process_rm returns None"""
    mock_utility.return_value.insert_log_table.return_value = IMPORT_ID
    
    result = rm_mod.rm_transformer(event_info)
    
    assert result is False
    mock_process_rm.assert_called_once_with(event_info)

@patch('src.room_metric.rm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.room_metric.rm_transformer.Utility')
@patch('src.room_metric.rm_transformer.process_rm', return_value=MagicMock(empty=True))
def test_rm_transformer_empty_dataframe(mock_process_rm, mock_utility, mock_check, event_info):
    """Test when process_rm returns empty DataFrame"""
    mock_utility.return_value.insert_log_table.return_value = IMPORT_ID
    
    result = rm_mod.rm_transformer(event_info)
    
    assert result is True
    mock_process_rm.assert_called_once_with(event_info)

@patch('src.room_metric.rm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.room_metric.rm_transformer.Utility')
@patch('src.room_metric.rm_transformer.log_and_send_email')
def test_rm_transformer_custom_exception(mock_log_email, mock_utility, mock_check, event_info):
    """Test custom exception handling in rm_transformer"""
    class CustomEx(Exception):
        pass
    
    rm_mod.custom_exceptions = CustomEx
    mock_utility.return_value.insert_log_table.side_effect = CustomEx('test error')
    
    result = rm_mod.rm_transformer(event_info)
    
    assert result is False
    mock_log_email.assert_called_once()

# ========== process_rm function tests ==========

@patch('src.room_metric.rm_transformer.get_rm_df', return_value=MagicMock())
@patch('src.room_metric.rm_transformer.Utility')
def test_process_rm_success_non_empty_df(mock_utility, mock_get_rm_df, event_info):
    """Test successful processing with non-empty DataFrame"""
    non_empty_df = MagicMock()
    non_empty_df.empty = False
    mock_utility.return_value.read_s3_file_common.return_value = (non_empty_df, 5)
    
    result = rm_mod.process_rm(event_info)
    
    assert result is not None
    assert event_info.room_metric_df == result
    mock_utility.return_value.read_s3_file_common.assert_called_once()
    mock_get_rm_df.assert_called_once_with(non_empty_df, event_info)

@patch('src.room_metric.rm_transformer.Utility')
def test_process_rm_empty_dataframe(mock_utility, event_info):
    """Test processing with empty DataFrame"""
    empty_df = MagicMock()
    empty_df.empty = True
    mock_utility.return_value.read_s3_file_common.return_value = (empty_df, 0)
    
    result = rm_mod.process_rm(event_info)
    
    assert result is empty_df
    assert event_info.room_metric_df == empty_df
    mock_utility.return_value.read_s3_file_common.assert_called_once()
    event_info.app_log.info.assert_called()

@patch('src.room_metric.rm_transformer.Utility')
def test_process_rm_none_dataframe(mock_utility, event_info):
    """Test processing when read_s3_file_common returns None"""
    mock_utility.return_value.read_s3_file_common.return_value = (None, 0)
    
    result = rm_mod.process_rm(event_info)
    
    assert result is None
    mock_utility.return_value.read_s3_file_common.assert_called_once()

@patch('src.room_metric.rm_transformer.log_and_send_email')
@patch('src.room_metric.rm_transformer.Utility')
def test_process_rm_custom_exception(mock_utility, mock_log_email, event_info):
    """Test custom exception handling in process_rm"""
    class CustomEx(Exception):
        pass
    
    rm_mod.custom_exceptions = CustomEx
    mock_utility.return_value.read_s3_file_common.side_effect = CustomEx('test error')
    
    result = rm_mod.process_rm(event_info)
    
    assert result is None
    mock_log_email.assert_called_once()

# ========== log_and_send_email function tests ==========

def test_log_and_send_email_success(event_info):
    """Test successful logging and email sending"""
    with patch('src.room_metric.rm_transformer.SendEmailNotification') as mock_send_email:
        mock_instance = MagicMock()
        mock_send_email.return_value = mock_instance
        
        rm_mod.log_and_send_email(event_info, 'test_action', 'test_message', Exception('test'))
        
        # Verify that app_log.error was called
        event_info.app_log.error.assert_called_once()
        # Verify that SendEmailNotification was called
        mock_send_email.assert_called_once()
        # Verify that execute was called on the SendEmailNotification instance
        mock_instance.execute.assert_called_once()

# ========== Additional edge case tests ==========

@patch('src.room_metric.rm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.room_metric.rm_transformer.Utility')
@patch('src.room_metric.rm_transformer.process_rm', return_value=MagicMock(empty=False))
def test_rm_transformer_logging_verification(mock_process_rm, mock_utility, mock_check, event_info):
    """Test that all logging calls are made correctly"""
    mock_utility.return_value.insert_log_table.return_value = IMPORT_ID
    mock_utility.return_value.upload_file_s3.return_value = True
    
    rm_mod.rm_transformer(event_info)
    
    # Verify all expected logging calls
    expected_calls = [
        call(event_info.trace_id, event_info.span_id, 'rm_transformer',
             f"Processing transformation for '{METRIC_TYPE}' metric for "
             f"'{INPUTFILE}' file of '{TENANT}' tenant_id and '{LOC}' location."),
        call(event_info.trace_id, event_info.span_id, 'rm_transformer',
             f"Original file name successfully checked for '{METRIC_TYPE}' "
             f"metric for '{INPUTFILE}' file has 'rawfile' raw filename of "
             f"'{TENANT}' tenant_id and '{LOC}' location."),
        call(event_info.trace_id, event_info.span_id, 'rm_transformer',
             f"Successfully completed transformation for '{METRIC_TYPE}' "
             f"metric for '{TENANT}' tenant_id and '{LOC}' location.")
    ]
    event_info.app_log.info.assert_has_calls(expected_calls)

@patch('src.room_metric.rm_transformer.get_rm_df', return_value=MagicMock())
@patch('src.room_metric.rm_transformer.Utility')
def test_process_rm_logging_verification(mock_utility, mock_get_rm_df, event_info):
    """Test that process_rm logging calls are made correctly"""
    non_empty_df = MagicMock()
    non_empty_df.empty = False
    mock_utility.return_value.read_s3_file_common.return_value = (non_empty_df, 5)
    
    rm_mod.process_rm(event_info)
    
    # Verify the logging call in process_rm
    event_info.app_log.info.assert_called_with(
        event_info.trace_id, event_info.span_id, 'process_rm',
        f"Processing for '{METRIC_TYPE}' metric for '{TENANT}' "
        f"tenant_id and '{LOC}' location."
    )

@patch('src.room_metric.rm_transformer.Utility')
def test_process_rm_empty_logging_verification(mock_utility, event_info):
    """Test that empty DataFrame logging is correct"""
    empty_df = MagicMock()
    empty_df.empty = True
    mock_utility.return_value.read_s3_file_common.return_value = (empty_df, 0)
    
    rm_mod.process_rm(event_info)
    
    # Verify the empty DataFrame logging call
    event_info.app_log.info.assert_called_with(
        event_info.trace_id, event_info.span_id, 'process_rm',
        f"TSA03 '{INPUTFILE}' file is empty for '{METRIC_TYPE}' metric with count '0' for "
        f"'{TENANT}' tenant_id and '{LOC}' location"
    )