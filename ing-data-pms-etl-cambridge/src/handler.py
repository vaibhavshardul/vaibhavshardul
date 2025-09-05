"""
Refactored Cambridge ETL Lambda Handler using common base classes.
This demonstrates how to reduce code duplication by inheriting from common base classes.
"""

import json

from action.event_analyzer import get_metric_file_dict, fetch_number_of_files
from action.event_processor import iterate_each_metric
from model.app_constants import AppConstants as Constants

from EtlServices.base_lambda_handler import BaseLambdaHandler
from EtlServices.etl_utilities import EtlUtilities as Utility
from EtlServices.common_params import CommonFunctions as common_func

custom_exceptions = Utility.custom_exceptions


class CambridgeLambdaHandler(BaseLambdaHandler):
    """
    Cambridge Lambda handler that extends BaseLambdaHandler.
    """

    def __init__(self):
        super().__init__("cambridge", master_request_id=Constants.MASTER_REQUEST_ID)


    def process_record(self, record, event_info):
        """
        Process a single SQS record for Cambridge.

        Args:
            record: SQS record to process
            event_info: Cambridge event information object
        """
        action = "process_record"
        event_info.request_event = request_event = json.loads(record["body"])

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                                f"Processing child request received for processing "
                                f"cambridge etl - {record}")
        event_info = common_func.assign_request_metadata(event_info, request_event)

        is_processing_success = self.extract_and_fetch_files(event_info)
        if not is_processing_success:
            self.handle_record_failure(event_info, request_event, None,
                                  update_documentdb=True)
            return
        iterate_each_metric(event_info)


    def extract_and_fetch_files(self, event_info):
        """
        This function is responsible for extracting location information, fetching the number of files,
        and getting a dictionary of metric files for further processing.

        Parameters:
        event_info (EventInfo): An object containing information about the event and its context.
            It contains attributes like trace_id, event_info.span_id, extract_req_ids, tenant_id,
            and location_code.

        Returns:
        bool: Returns True if all the operations are successful, otherwise False.
        """
        action = "extract_and_fetch_files"
        try:
            cambridge_extract_location_info_success = Utility(
                event_info.app_log).extract_location_info(event_info)
            if not cambridge_extract_location_info_success:
                return False

            cambridge_fetch_number_of_files_success = fetch_number_of_files(event_info)
            if not cambridge_fetch_number_of_files_success:
                return False

            cambridge_get_metric_file_dict_success = get_metric_file_dict(event_info)
            if not cambridge_get_metric_file_dict_success:
                return False

            return True

        except custom_exceptions as e:
            record = event_info.app_log.error(event_info.trace_id, event_info.span_id, action,
                                              f"Exception while evaluating extracting and "
                                              f"fetching the files. The Error "
                                              f"{e}")
            SendEmailNotification(record).execute()
            return False


# Create handler instance
handler_instance = CambridgeLambdaHandler()

def lambda_handler(event, context):
    """
    AWS Lambda entry point for Cambridge ETL processing.
    """
    return handler_instance.lambda_handler(event, context)