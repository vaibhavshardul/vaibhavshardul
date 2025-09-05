"""Transformation logic for the Room metrics"""
from EtlServices.etl_utilities import EtlUtilities as Utility
from EtlServices.fpg_ing_mysql import FpgIngMySQL
from Notifications.email_send import SendEmailNotification
from action.event_analyzer import get_rm_df, check_original_file_name
from model.app_constants import AppConstants as Constants

ing_db_mysql = FpgIngMySQL()
custom_exceptions = Utility.custom_exceptions

def rm_transformer(event_info):
    """
        Performs transformation logic for RM (Room Metric) based on the provided event information.
    """
    action = "rm_transformer"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Processing transformation for '{event_info.metric_type}' metric for "
                     f"'{event_info.input_file_name}' file of '{tenant_id}' tenant_id and "
                     f"'{location_code}' location.")

        event_info.raw_file_name = check_original_file_name(event_info, "RM")

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Original file name successfully checked for '{event_info.metric_type}' "
                     f"metric for '{event_info.input_file_name}' file has '"
                     f"{event_info.raw_file_name}' raw filename of '{tenant_id}' tenant_id and '"
                     f"{location_code}' location.")

        event_info.output_metric = "ROOM_METRIC"
        event_info.entity_type = 47

        event_info.import_id = Utility(event_info.app_log).insert_log_table(event_info,
                                                        Constants.DB_ING_TBL_IMPORTED_FILE_LOG)
        if event_info.import_id is None:
            return False

        output_df = process_rm(event_info)

        if output_df is None:
            return False
        elif output_df.empty:
            status = True
        else:
            status = Utility(event_info.app_log).upload_file_s3(output_df, event_info)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Successfully completed transformation for '{event_info.metric_type}' "
                     f"metric for '{tenant_id}' tenant_id and '{location_code}' location.")

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while processing '{event_info.metric_type}' metric for '"
                           f"{tenant_id}' tenant_id and '{location_code}' location.",
                           e)
        status = False

    return status


def process_rm(event_info):
    """
        Processes Room Metric (RM) based on the provided event information
    """
    action = "process_rm"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    rm_df = None
    rm_df_count = 0

    try:
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Processing for '{event_info.metric_type}' metric for '{tenant_id}' "
                     f"tenant_id and '{location_code}' location.")
        for item in event_info.file_dict_list:
            rm_df, rm_df_count = Utility(event_info.app_log).read_s3_file_common(event_info,
                                                item, delimiter="\t", use_global_s3=True,
                                                        no_header_row=True, quoting_required=True)

        if rm_df is None:
            return None
        elif rm_df.empty:
            event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                         f"TSA03 '{event_info.input_file_name}' file is empty for '"
                         f"{event_info.metric_type}' metric with count '{rm_df_count}' for '"
                         f"{tenant_id}' tenant_id and '{location_code}' location")
            event_info.room_metric_df = rm_df
            return rm_df
        else:
            rm_df = get_rm_df(rm_df, event_info)

        event_info.room_metric_df = rm_df

        return rm_df

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while processing '{event_info.metric_type}' metric for '"
                           f"{tenant_id}' tenant_id and '{location_code}' location.",
                           e)
        return None


def log_and_send_email(event_info, action, message, exception):
    """
    Logs an error and sends an email notification.
    """
    record = event_info.app_log.error(event_info.trace_id, event_info.span_id, action, message, exception)
    SendEmailNotification(record).execute()
