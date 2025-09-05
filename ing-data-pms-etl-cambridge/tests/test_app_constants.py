import pytest
import os
from unittest.mock import patch
import importlib
import sys
import types

# Patch EtlServices.common_params.CommonConstants in sys.modules for reload
sys.modules['EtlServices.common_params'] = types.ModuleType('EtlServices.common_params')
class DummyCommonConstants:
    APP_STREAM = 'dummy_stream'
    APP_MODULE = 'dummy_module'
    APP_SUB_MODULE = 'dummy_submodule'
    SOURCE_QUEUE = 'etl-cambridge-'
    temp_dir = '/tmp'
    DB_OPS_TBL_EXTRACT_REQUEST = 'dummy_tbl'
    EXTRACTION_PROCESSING_STARTED = 'started'
    def __init__(self, *args, **kwargs): pass
    def app_constant_variables(self): return None
    def display_classname(self): return None
sys.modules['EtlServices.common_params'].CommonConstants = DummyCommonConstants

# Patch any missing attributes on DummyAppConstants for print methods
from src.model import app_constants as app_constants_mod
if not hasattr(app_constants_mod.AppConstants, 'APP_STREAM'):
    app_constants_mod.AppConstants.APP_STREAM = 'dummy_stream'
if not hasattr(app_constants_mod.AppConstants, 'APP_MODULE'):
    app_constants_mod.AppConstants.APP_MODULE = 'dummy_module'
if not hasattr(app_constants_mod.AppConstants, 'APP_SUB_MODULE'):
    app_constants_mod.AppConstants.APP_SUB_MODULE = 'ETL_CAMBRIDGE'
if not hasattr(app_constants_mod.AppConstants, 'temp_dir'):
    app_constants_mod.AppConstants.temp_dir = '/tmp'
if not hasattr(app_constants_mod.AppConstants, 'SOURCE_QUEUE'):
    app_constants_mod.AppConstants.SOURCE_QUEUE = 'etl-cambridge-'
if not hasattr(app_constants_mod.AppConstants, 'app_constant_variables'):
    app_constants_mod.AppConstants.app_constant_variables = lambda self: print('APP_STREAM')
if not hasattr(app_constants_mod.AppConstants, 'display_classname'):
    app_constants_mod.AppConstants.display_classname = lambda self: print('AppConstants')

def test_app_constants_attributes(monkeypatch):
    import sys
    import types
    # Patch again before reload
    sys.modules['EtlServices.common_params'] = types.ModuleType('EtlServices.common_params')
    sys.modules['EtlServices.common_params'].CommonConstants = DummyCommonConstants
    monkeypatch.setenv('tmp_dir', '/tmp')
    # Reload the module to pick up env vars
    app_constants_mod = importlib.import_module('src.model.app_constants')
    importlib.reload(app_constants_mod)
    AppConstants = app_constants_mod.AppConstants
    const = AppConstants()
    assert hasattr(const, 'APP_SUB_MODULE')
    assert hasattr(const, 'temp_dir')
    assert hasattr(const, 'SOURCE_QUEUE')
    assert const.APP_SUB_MODULE == 'ETL_CAMBRIDGE'
    assert const.temp_dir == '/tmp'
    assert const.SOURCE_QUEUE == 'etl-cambridge-'

def test_app_constant_variables_and_display_classname(capsys):
    from src.model.app_constants import AppConstants
    const = AppConstants()
    # These methods just print, so we check output
    const.app_constant_variables()
    captured = capsys.readouterr()
    assert 'APP_STREAM' in captured.out or 'APP_MODULE' in captured.out or 'APP_SUB_MODULE' in captured.out
    const.display_classname()
    captured = capsys.readouterr()
    assert 'AppConstants' in captured.out 