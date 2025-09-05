"""Transformation logic for the Agent metrics"""
from EtlServices.etl_utilities import EtlUtilities as Utility
from EtlServices.fpg_ing_mysql import FpgIngMySQL
from Notifications.email_send import SendEmailNotification
from action.event_analyzer import get_tsa06_df, check_original_file_name
from model.app_constants import AppConstants as Constants


ing_db_mysql = FpgIngMySQL()
custom_exceptions = Utility.custom_exceptions


def am_transformer(event_info):
    """
    Transform the data for the given event information and log the process.
    @param event_info - Information about the event
    @return True if the transformation is successful, False otherwise.
    """
    action = "am_transformer"

    try:
        tenant_id = event_info.tenant_id
        location_code = event_info.location_code
        metric_type = event_info.metric_type
        input_file_name = event_info.input_file_name

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Processing transformation for '{metric_type}' metric for '"
                     f"{input_file_name}' file of '{tenant_id}' tenant_id and '{location_code}' "
                     f"location.")

        # DLDP-1253 : Checking Original File Name
        event_info.raw_file_name = check_original_file_name(event_info, "AM")

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Original file name successfully checked for '{metric_type}' metric for '"
                     f"{input_file_name}' file has '{event_info.raw_file_name}' raw filename of "
                     f"'{tenant_id}' tenant_id and '{location_code}' location.")

        event_info.output_metric = "AGENT_METRIC"
        event_info.entity_type = 3

        # creating entry in imported_file_log table
        event_info.import_id = Utility(event_info.app_log).insert_log_table(event_info,
                                                        Constants.DB_ING_TBL_IMPORTED_FILE_LOG)

        if event_info.import_id is None:
            return False

        output_df = process_am(event_info)

        if output_df is None:
            return False
        elif output_df.empty:
            status = False
            event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                         f"Could not process TSA06 since file is empty for '{metric_type}' metric "
                         f"for '{input_file_name}' file of '{tenant_id}' tenant_id and '"
                         f"{location_code}' location.")
        else:
            status = Utility(event_info.app_log).upload_file_s3(output_df, event_info)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Successfully completed transformation for '{metric_type}' metric for '"
                     f"{input_file_name}' file of '{tenant_id}' tenant_id and '{location_code}' "
                     f"location.")

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while transforming '{metric_type}' metric for '"
                           f"{input_file_name}' file for '{tenant_id}' tenant_id and '"
                           f"{location_code}' location.",
                           e)
        status = False

    return status


def process_am(event_info):
    """
    Process the Asset Management event information.
    @param event_info - the event information containing trace_id, span_id, file_dict_list,
    metric_type, input_file_name, tenant_id, and location_code.
    @return tsa06_df - the processed Asset Management data frame.
    """
    action = "process_am"
    tsa06_df = None

    try:
        for item in event_info.file_dict_list:
            tsa06_df, tsa06_df_count = Utility(event_info.app_log).read_s3_file_common(event_info,
                                                item, delimiter="\t", use_global_s3=True,
                                                        no_header_row=True, quoting_required=True)

        if tsa06_df is None:
            return None
        elif tsa06_df.empty:
            event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                         f"TSA06 dataframe is empty with count '{tsa06_df_count}' for '"
                         f"{event_info.metric_type}' metric for '{event_info.input_file_name}' "
                         f"file of '{event_info.tenant_id}' tenant_id and '"
                         f"{event_info.location_code}' location.")
        else:
            tsa06_df = get_tsa06_df(tsa06_df, event_info)

        return tsa06_df

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while processing '{event_info.metric_type}' metric for '"
                           f"{event_info.input_file_name}' file of '{event_info.tenant_id}' "
                           f"tenant_id and '{event_info.location_code}' location.",
                           e)
        return None


def log_and_send_email(event_info, action, message, exception=None):
    """
    Log an error message and send an email notification with the provided event information,
    action, message, and exception.
    @param event_info - Information about the event
    @param action - The action being logged
    @param message - The message to log
    @param exception - The exception that occurred (optional)
    @return None
    """
    record = event_info.app_log.error(event_info.trace_id, event_info.span_id, action, message, exception)
    SendEmailNotification(record).execute()
