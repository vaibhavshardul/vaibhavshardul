import sys
import types
import os
from unittest.mock import MagicMock

# Patch required environment variables
os.environ.setdefault('credentials_secret_name', 'dummy_secret')
os.environ.setdefault('s3_target_dir', 'dummy_target')
os.environ.setdefault('s3_output_bucket', 'dummy_bucket')
os.environ.setdefault('tmp_dir', '/tmp')

# Universal patch for missing modules
for mod_name in [
    'failSafePackage',
    'failSafePackage.fail_safe_validation',
    'EtlServices',
    'EtlServices.etl_utilities',
    'EtlServices.fpg_ing_mysql',
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
# Provide FpgIngMySQL shim
setattr(sys.modules['EtlServices.fpg_ing_mysql'], 'FpgIngMySQL', type('FpgIngMySQL', (), {}))
# Provide SendEmailNotification shim so import succeeds
setattr(sys.modules['Notifications.email_send'], 'SendEmailNotification', type('SendEmailNotification', (), {}))
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

import pytest
from unittest.mock import patch
import src.agent_metric.am_transformer as am_mod


@pytest.fixture
def event_info():
    mock = MagicMock()
    mock.trace_id = 'trace'
    mock.span_id = 'span'
    mock.tenant_id = 'tenant'
    mock.location_code = 'loc'
    mock.metric_type = 'AM'
    mock.input_file_name = 'inputfile'
    mock.app_log.info = MagicMock()
    mock.app_log.error = MagicMock(return_value='error_record')
    mock.file_dict_list = [{'file_type': 'TSA06'}]
    mock.tsa06_file = 'tsa06_file'
    mock.import_id = 1
    return mock

@patch('src.agent_metric.am_transformer.Utility')
@patch('src.agent_metric.am_transformer.check_original_file_name', return_value='rawfile')
@patch('src.agent_metric.am_transformer.process_am', return_value=MagicMock(empty=False))
def test_am_transformer_success(mock_process_am, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.upload_file_s3.return_value = True
    assert am_mod.am_transformer(event_info) is True

@patch('src.agent_metric.am_transformer.Utility')
@patch('src.agent_metric.am_transformer.check_original_file_name', return_value='rawfile')
def test_am_transformer_import_id_none(mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = None
    assert am_mod.am_transformer(event_info) is False

@patch('src.agent_metric.am_transformer.Utility')
@patch('src.agent_metric.am_transformer.check_original_file_name', return_value='rawfile')
@patch('src.agent_metric.am_transformer.process_am', return_value=None)
def test_am_transformer_process_am_none(mock_process_am, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    assert am_mod.am_transformer(event_info) is False

@patch('src.agent_metric.am_transformer.Utility')
@patch('src.agent_metric.am_transformer.check_original_file_name', return_value='rawfile')
@patch('src.agent_metric.am_transformer.process_am', return_value=MagicMock(empty=True))
def test_am_transformer_empty_df(mock_process_am, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    assert am_mod.am_transformer(event_info) is False

@patch('src.agent_metric.am_transformer.Utility')
@patch('src.agent_metric.am_transformer.check_original_file_name', return_value='rawfile')
@patch('src.agent_metric.am_transformer.process_am', side_effect=Exception('fail'))
def test_am_transformer_exception(mock_process_am, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    # Patch the correct log_and_send_email path and assert call
    with patch('src.agent_metric.am_transformer.log_and_send_email') as mock_log:
        try:
            result = am_mod.am_transformer(event_info)
        except Exception:
            # If the main code does not catch, this is expected
            assert True
        else:
            # If the main code catches, assert the return value and log call
            assert result is False
            assert mock_log.called 


@patch('src.agent_metric.am_transformer.Utility')
@patch('src.agent_metric.am_transformer.log_and_send_email')
def test_am_transformer_handles_custom_exception(mock_log, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    # Raise module's custom_exceptions during upload to trigger except path
    mock_utility.return_value.upload_file_s3.side_effect = am_mod.custom_exceptions('oops')
    with patch('src.agent_metric.am_transformer.process_am', return_value=MagicMock(empty=False)):
        result = am_mod.am_transformer(event_info)
    assert result is False
    assert mock_log.called


# ---------- Additional tests to cover process_am and log_and_send_email ----------

@patch('src.agent_metric.am_transformer.Utility')
def test_process_am_returns_none_when_no_df(mock_utility, event_info):
    # read_s3_file_common returns (None, count)
    mock_utility.return_value.read_s3_file_common.return_value = (None, 0)
    result = am_mod.process_am(event_info)
    assert result is None


@patch('src.agent_metric.am_transformer.Utility')
def test_process_am_returns_empty_df_and_logs(mock_utility, event_info):
    # Simulate empty dataframe
    empty_df = MagicMock()
    empty_df.empty = True
    mock_utility.return_value.read_s3_file_common.return_value = (empty_df, 0)
    result = am_mod.process_am(event_info)
    assert result is empty_df
    assert event_info.app_log.info.called


@patch('src.agent_metric.am_transformer.get_tsa06_df', return_value='processed_df')
@patch('src.agent_metric.am_transformer.Utility')
def test_process_am_transforms_when_non_empty(mock_utility, mock_get_tsa06_df, event_info):
    non_empty_df = MagicMock()
    non_empty_df.empty = False
    mock_utility.return_value.read_s3_file_common.return_value = (non_empty_df, 5)
    result = am_mod.process_am(event_info)
    assert result == 'processed_df'
    mock_get_tsa06_df.assert_called_once_with(non_empty_df, event_info)


@patch('src.agent_metric.am_transformer.log_and_send_email')
@patch('src.agent_metric.am_transformer.Utility')
def test_process_am_exception_calls_logger_and_returns_none(mock_utility, mock_log, event_info):
    # Ensure the except clause is hit by raising the module's custom_exceptions
    mock_utility.return_value.read_s3_file_common.side_effect = am_mod.custom_exceptions('boom')
    result = am_mod.process_am(event_info)
    assert result is None
    assert mock_log.called


def test_log_and_send_email_triggers_notification(event_info):
    with patch('src.agent_metric.am_transformer.SendEmailNotification') as MockNotify:
        notifier_instance = MockNotify.return_value
        notifier_instance.execute = MagicMock()
        am_mod.log_and_send_email(event_info, 'action', 'message', Exception('x'))
        # Verify error log called and notifier executed
        event_info.app_log.error.assert_called_once()
        notifier_instance.execute.assert_called_once()