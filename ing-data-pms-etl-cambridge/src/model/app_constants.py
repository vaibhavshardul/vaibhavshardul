"""Initialise the constants used in the processing environment"""
import os
from EtlServices.common_params import CommonConstants

class AppConstants(CommonConstants):
    """
    A class to store application constants used throughout the ETL process.

    Attributes:
        APP_STREAM (str): Name of the application stream.
        APP_MODULE (str): Name of the application module.
        APP_SUB_MODULE (str): Name of the application sub-module.

        DB_OPS_TBL_EXTRACT_REQUEST (str): Table name for extract requests in the database.
        DB_OPS_TBL_CLIENT_INFO_MASTER (str): Table name for client information master in the
        database.

        DB_ING_TBL_PROCESSED_FILE_LOG (str): Table name for processed file logs in the database.
        DB_ING_TBL_IMPORTED_FILE_LOG (str): Table name for imported file logs in the database.

        EXTRACTION_PROCESSING_FAILURE (str): Status message for extraction processing failure.
        EXTRACTION_PROCESSING_STARTED (str): Status message for extraction processing start.
        EXTRACTION_PROCESSING_SUCCESS (str): Status message for extraction processing success.

        MASTER_REQUEST_ID (str): Unique identifier for the master request.

        temp_dir (str): Temporary directory path.
        SOURCE_QUEUE (str): Prefix for the source queue name.
    """
    APP_SUB_MODULE = "ETL_CAMBRIDGE"

    temp_dir = os.environ.get("tmp_dir")
    SOURCE_QUEUE = "etl-cambridge-"

    def app_constant_variables(self):
        """
        This method prints the application constants: APP_STREAM, APP_MODULE, and APP_SUB_MODULE.

        Parameters:
        self (AppConstants): The instance of the AppConstants class.

        Returns:
        None: This method does not return any value. It only prints the application constants.
        """
        print(f"The APP_STREAM is :  {self.APP_STREAM}")
        print(f"The APP_MODULE is :  {self.APP_MODULE}")
        print(f"The APP_SUB_MODULE is :  {self.APP_SUB_MODULE}")

    def display_classname(self):
        """
        This method prints the name of the class (AppConstants).
        """
        print(self.__class__.__name__)
