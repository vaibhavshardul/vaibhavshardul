"""utitility functions used to analyse or do the initial manipulation on the data"""
from EtlServices.etl_utilities import EtlUtilities as Utility
from Notifications.email_send import SendEmailNotification
from action.event_analyzer import extract_file_info
from agent_metric.am_transformer import am_transformer
from location_metric.lm_transformer import lm_transformer
from model.app_constants import AppConstants as Constants
from product_metric.pm_transformer import pm_transformer
from room_metric.rm_transformer import rm_transformer

custom_exceptions = Utility.custom_exceptions


def log_and_send_email(event_info, action, message, exception):
    """
    Log an error and send an email notification.
    """
    record = event_info.app_log.error(event_info.trace_id, event_info.span_id, action, message, exception)
    SendEmailNotification(record).execute()


def call_transform_code(event_info):
    """
    Execute the transformation code based on the event information provided.
    @param event_info - Information about the event triggering the transformation.
    @return None
    """
    action = "call_transform_code"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    metric_type = event_info.metric_type
    start_msg = f"Calling '{metric_type}' transformation for '{tenant_id}' tenant_id and '" \
                f"{location_code}' location."
    error_msg = f"Error while calling transformation for '{metric_type}' metric for '{tenant_id}'" \
                f" tenant_id and '{location_code}' location"
    unsupported_msg = f"Unsupported '{metric_type}' metric type received for '{tenant_id}' " \
                      f"tenant_id and '{location_code}' location. Request terminated."

    try:
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action, start_msg)

        if metric_type == "PM":
            status = pm_transformer(event_info)
        elif metric_type == "LM":
            status = lm_transformer(event_info)
        elif metric_type == "AM":
            status = am_transformer(event_info)
        elif metric_type == "RM":
            status = rm_transformer(event_info)
        else:
            raise ValueError(unsupported_msg)

    except custom_exceptions as e:
        log_and_send_email(event_info, action, error_msg, e)
        status = False

    return status


def call_api(event_info):
    """
    Call an API with the provided event information and handle any exceptions that occur during
    the process.
    @param event_info - Information about the event
    @return None
    """
    action = "call_api"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    output_file_name = event_info.output_file_name
    api_skip_msg = f"Skipping the API call as it is '{event_info.metric_type}' metric of '" \
                   f"{output_file_name}' file for '{tenant_id}' tenant_id and '{location_code}' " \
                   f"location."
    api_error_msg = f"Failed to post request to api of '{output_file_name}' file for '" \
                    f"{tenant_id}' tenant_id and '{location_code}' location"

    is_processing_success = True

    try:
        # creating entry in processed_file_log table
        event_info.processed_id = Utility(event_info.app_log).insert_log_table(event_info,
                                                           Constants.DB_ING_TBL_PROCESSED_FILE_LOG)

        if event_info.processed_id is None:
            return False
        else:
            if event_info.entity_type == 47:
                if not event_info.room_metric_df.empty:
                    is_processing_success = Utility(event_info.app_log).update_processed_file_log_table(event_info)
                    event_info.app_log.info(event_info.trace_id, event_info.span_id, action, api_skip_msg)
                else:
                    is_processing_success = True
            else:
                # calling api
                is_processing_success = Utility(event_info.app_log).post_the_request_to_api(event_info)

    except custom_exceptions as e:
        log_and_send_email(event_info, action, api_error_msg, e)
        is_processing_success = False

    return is_processing_success


def iterate_each_metric(event_info):
    """
    Iterate through each metric in the event information and process the files received for
     "{} that
    metric. If an exception occurs during processing, log an error and send an email notification.
    @param event_info - Information about the event
    @return None
    """
    action = "iterate_each_metric"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    for metric, files_received in event_info.metric_file_dict.items():
        try:
            iterate_msg = f"Iterating files for '{metric}' metric. Files received: " \
                          f"{len(files_received)} for '{tenant_id}' tenant_id " \
                          f"and '{location_code}' location."
            event_info.app_log.info(event_info.trace_id, event_info.span_id, action, iterate_msg)

            process_files(metric, files_received, event_info)

        except custom_exceptions as e:
            error_msg = f"Failed to iterate for '{metric}' metric for '{files_received}' files " \
                        f"for '{tenant_id}' tenant_id and '{location_code}' location."
            log_and_send_email(event_info, action, error_msg, e)


def process_files(metric, files_received, event_info):
    """
    Process the files received based on the given metric and event information.
    @param metric - the type of metric being processed
    @param files_received - the list of files received
    @param event_info - information about the event
    @return None
    """
    event_info.metric_type = metric
    event_info.file_dict_list = files_received
    event_info.file_dict = files_received[-1]
    event_info.upload_s3_bucket_name = event_info.file_dict['s3_bucket_name']
    event_info.upload_file_object = event_info.file_dict['file_object']

    is_processing_success = extract_file_info(metric, event_info)
    if not is_processing_success:
        update_extraction_status(event_info, files_received,
                                 Constants.EXTRACTION_PROCESSING_FAILURE)
        return

    is_processing_success = call_transform_code(event_info)
    if not is_processing_success:
        update_extraction_status(event_info, files_received,
                                 Constants.EXTRACTION_PROCESSING_FAILURE)
        return

    is_processing_success = call_api(event_info)
    if not is_processing_success:
        update_extraction_status(event_info, files_received,
                                 Constants.EXTRACTION_PROCESSING_FAILURE)
        return

    cleanup_and_update(event_info, files_received)


def update_extraction_status(event_info, files_received, status):
    """
    Update the extraction status for the files received in the event information.
    @param event_info - Information about the event
    @param files_received - List of files received
    @param status - The status to update to
    """
    for files in files_received:
        Utility(event_info.app_log).update_extract_request(event_info, files["req_id"], status)


def cleanup_and_update(event_info, files_received):
    """
    Perform cleanup and update operations after processing files received during an event.
    @param event_info - Information about the event being processed.
    @param files_received - List of files received during the event.
    This function deletes temporary files associated with the event, updates the extraction
    request status for each file received, and updates the client information master record.
    """
    Utility(event_info.app_log).delete_temp_file(event_info)
    for files in files_received:
        Utility(event_info.app_log).update_extract_request(event_info, files["req_id"],
                                       Constants.EXTRACTION_PROCESSING_SUCCESS)
    Utility(event_info.app_log).update_client_info_master(event_info)
