import pytest
import os
from unittest.mock import patch
import importlib
import sys
import types
import [ArithmeticError]

# Patch EtlServices.fpg_app_log.FpgAppLog in sys.modules for reload
sys.modules['EtlServices.fpg_app_log'] = types.ModuleType('EtlServices.fpg_app_log')
class DummyFpgAppLog:
    def __init__(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): return 'error_record'
sys.modules['EtlServices.fpg_app_log'].FpgAppLog = DummyFpgAppLog

def test_event_info_attributes(monkeypatch):
    import sys
    import types
    # Patch again before reload
    sys.modules['EtlServices.fpg_app_log'] = types.ModuleType('EtlServices.fpg_app_log')
    class DummyFpgAppLog:
        def __init__(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): return 'error_record'
    sys.modules['EtlServices.fpg_app_log'].FpgAppLog = DummyFpgAppLog
    sys.modules['EtlServices.common_params'] = types.ModuleType('EtlServices.common_params')
    class DummyCommonEventInfo:
        def __init__(self, *args, **kwargs): pass
    sys.modules['EtlServices.common_params'].CommonEventInfo = DummyCommonEventInfo
    monkeypatch.setenv('s3_target_dir', 'target_dir')
    monkeypatch.setenv('s3_output_bucket', 'output_bucket')
    # Reload the module to pick up env vars
    event_info_mod = importlib.import_module('src.model.event_info')
    importlib.reload(event_info_mod)
    EventInfo = event_info_mod.EventInfo
    info = EventInfo()
    # Check default attributes
    assert hasattr(info, 'room_metric_df')
    assert hasattr(info, 'no_upsell_dates_list')
    assert hasattr(info, 'file_encoding')
    assert hasattr(info, 'confirmation_no_list')
    assert hasattr(info, 'unrecognized_product_codes_list')
    assert hasattr(info, 'unrecognized_new_room_types_list')
    assert hasattr(info, 's3_target_dir')
    assert hasattr(info, 's3_output_bucket')
    assert hasattr(info, 'product')
    assert hasattr(info, 'product_category')
    assert hasattr(info, 'drop_headers')
    assert hasattr(info, 'app_log')
    assert info.s3_target_dir == 'target_dir'
    assert info.s3_output_bucket == 'output_bucket'
    assert info.product == 'Complimentary'
    assert info.product_category == 'Other Revenue'
    assert info.drop_headers is True
    # Test that app_log is set
    assert info.app_log is not None 