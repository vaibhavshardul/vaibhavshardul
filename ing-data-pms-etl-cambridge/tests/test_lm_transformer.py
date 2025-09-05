import sys
import types
import os
from unittest.mock import MagicMock

# Patch required environment variables
os.environ.setdefault('credentials_secret_name', 'dummy_secret')
os.environ.setdefault('s3_target_dir', 'dummy_target')
os.environ.setdefault('s3_output_bucket', 'dummy_bucket')
os.environ.setdefault('tmp_dir', '/tmp')

import pytest
from unittest.mock import patch
import src.location_metric.lm_transformer as lm_mod

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

# Add dummy AppConstants class for transformer tests
class DummyAppConstants:
    DB_ING_TBL_IMPORTED_FILE_LOG = 'imported_file_log'
setattr(sys.modules['model.app_constants'], 'AppConstants', DummyAppConstants)

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

@pytest.fixture
def event_info():
    mock = MagicMock()
    mock.trace_id = 'trace'
    mock.span_id = 'span'
    mock.tenant_id = 'tenant'
    mock.location_code = 'loc'
    mock.metric_type = 'LM'
    mock.input_file_name = 'inputfile'
    mock.app_log.info = MagicMock()
    mock.app_log.error = MagicMock(return_value='error_record')
    mock.file_dict_list = [{'file_type': 'TSA04'}, {'file_type': 'TSA03'}]
    mock.tsa04_available = True
    mock.tsa03_available = True
    mock.tsa04_file = 'tsa04_file'
    mock.tsa03_file = 'tsa03_file'
    mock.import_id = 1
    return mock

@patch('src.location_metric.lm_transformer.Utility')
@patch('src.location_metric.lm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.location_metric.lm_transformer.process_lm', return_value=MagicMock(empty=False))
def test_lm_transformer_success(mock_process_lm, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    mock_utility.return_value.upload_file_s3.return_value = True
    assert lm_mod.lm_transformer(event_info) is True

@patch('src.location_metric.lm_transformer.Utility')
@patch('src.location_metric.lm_transformer.check_original_file_name', return_value='rawfile')
def test_lm_transformer_import_id_none(mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = None
    assert lm_mod.lm_transformer(event_info) is False

@patch('src.location_metric.lm_transformer.Utility')
@patch('src.location_metric.lm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.location_metric.lm_transformer.process_lm', return_value=None)
def test_lm_transformer_process_lm_none(mock_process_lm, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    assert lm_mod.lm_transformer(event_info) is False

@patch('src.location_metric.lm_transformer.Utility')
@patch('src.location_metric.lm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.location_metric.lm_transformer.process_lm', return_value=MagicMock(empty=True))
def test_lm_transformer_empty_df(mock_process_lm, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    assert lm_mod.lm_transformer(event_info) is False

@patch('src.location_metric.lm_transformer.Utility')
@patch('src.location_metric.lm_transformer.check_original_file_name', return_value='rawfile')
@patch('src.location_metric.lm_transformer.process_lm', side_effect=Exception('fail'))
def test_lm_transformer_exception(mock_process_lm, mock_check, mock_utility, event_info):
    mock_utility.return_value.insert_log_table.return_value = 1
    with pytest.raises(Exception):
        lm_mod.lm_transformer(event_info) 