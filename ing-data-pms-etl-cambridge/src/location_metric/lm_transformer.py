"""Transformation logic for the Location metrics"""
import pandas as pd
from EtlServices.etl_utilities import EtlUtilities as Utility
from EtlServices.fpg_ing_mysql import FpgIngMySQL
from EtlServices.fpg_ops_mongo import FpgOpsMongo
from Notifications.email_send import SendEmailNotification
from failSafePackage.fail_safe_validation import fail_safe_cls
from action.event_analyzer import get_tsa03_df, get_tsa04_df, \
    check_original_file_name
from model.app_constants import AppConstants as Constants

ops_db_mongo = FpgOpsMongo()
ing_db_mysql = FpgIngMySQL()
custom_exceptions = Utility.custom_exceptions


def lm_transformer(event_info):
    """
    Transform the event information using a transformer function.
    @param event_info - the event information to be transformed
    @return None
    """
    action = "lm_transformer"

    try:
        input_file_name = event_info.input_file_name
        tenant_id = event_info.tenant_id
        metric_type = event_info.metric_type
        location_code = event_info.location_code

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Processing transformation for '{metric_type}' metric for '{tenant_id}' "
                     f"tenant_id and '{location_code}' location.")

        # SHUBHAM DLDP-789-missing_pms_p2 Get original_file_name here.
        event_info.raw_file_name = check_original_file_name(event_info, "LM")

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Original file name successfully checked for '{metric_type}' metric for '"
                     f"{input_file_name}' file has '{event_info.raw_file_name}' raw filename of "
                     f"'{tenant_id}' tenant_id and '{location_code}' location.")

        event_info.output_metric = "LOCATION_METRIC"
        event_info.entity_type = 2

        # creating entry in imported_file_log table
        event_info.import_id = Utility(event_info.app_log).insert_log_table(event_info,
                                                        Constants.DB_ING_TBL_IMPORTED_FILE_LOG)

        if event_info.import_id is None:
            return False

        output_df = process_lm(event_info)

        if output_df is None:
            status = False
        elif output_df.empty:
            status = False
            event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                         f"Could not process, since TSA04 file is empty for '{metric_type}' "
                         f"metric for '{input_file_name}' file of '{tenant_id}' tenant_id and '"
                         f"{location_code}' location.")
        else:
            status = Utility(event_info.app_log).upload_file_s3(output_df, event_info)

    except custom_exceptions as e:
        record = event_info.app_log.error(event_info.trace_id, event_info.span_id, action,
                               f"Exception while transforming '{metric_type}' metric for '"
                               f"{tenant_id}' tenant_id and '{location_code}' location.",
                               e)
        SendEmailNotification(record).execute()
        status = False

    return status


def process_lm(event_info):
    """
    Process the event information and log the processing status. If an exception occurs during
    processing, log the error and send an email notification.
    @param event_info - Information about the event
    @return The processed dataframe
    """
    action = "process_lm"
    tsa04_df = None
    tsa03_df = None

    try:
        for item in event_info.file_dict_list:
            processed_df, empty_file_status = process_file(event_info, item)
            if empty_file_status:
                return processed_df
            if item["file_type"] == "TSA04":
                tsa04_df = processed_df
            else:
                tsa03_df = processed_df

        # Return None if TSA04 is not available or its DataFrame is empty
        if not event_info.tsa04_available or (tsa04_df is not None and tsa04_df.empty):
            return None

        input_df = merge_dataframes(tsa04_df, tsa03_df, event_info)
        input_df = add_additional_columns(input_df)
        input_df["Date"] = input_df["Date"].apply(
            fail_safe_cls(errors="coerce").daily_date_validation)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Successfully completed processing '{event_info.metric_type}' metric for '"
                     f"{event_info.tenant_id}' tenant_id and '{event_info.location_code}' "
                     f"location and count is: {str(len(input_df))}")
        return input_df

    except custom_exceptions as e:
        record = event_info.app_log.error(event_info.trace_id, event_info.span_id, action,
                               f"Exception while processing '{event_info.metric_type}' metric for "
                               f"'{event_info.tenant_id}' tenant_id and '"
                               f"{event_info.location_code}' location",
                               e)
        SendEmailNotification(record).execute()
        return None


def process_file(event_info, item):
    """
    Process an individual file based on its type and handle the DataFrame creation or return
    early if conditions are met.
    @param event_info - information about the event
    @param item - the file item to be processed
    @return tsa_df - the processed DataFrame
    @return A boolean value indicating whether the processing was successful or not.
    """
    file_type = item["file_type"]
    tsa_df = process_tsa_file(event_info, item, file_type)

    # Early return if DataFrame is None or empty for TSA04
    if file_type == "TSA04" and (tsa_df is None or tsa_df.empty):
        return tsa_df, True
    # Early return if DataFrame is None for TSA03
    elif file_type != "TSA04" and tsa_df is None:
        return None, True

    return tsa_df, False


def process_tsa_file(event_info, item, file_type):
    """
    Process a TSA file based on the event information, item, and file type provided.
    @param event_info - Information about the event
    @param item - The item to process
    @param file_type - The type of TSA file (TSA04 or TSA03)
    @return The processed TSA dataframe
    """
    tsa_df, _ = Utility(event_info.app_log).read_s3_file_common(event_info,
                                                item, delimiter="\t", use_global_s3=True,
                                                        no_header_row=True, quoting_required=True)

    if tsa_df is None or tsa_df.empty:
        return tsa_df

    if file_type == "TSA04":
        event_info.tsa04_file = item["file_object"]
        tsa_df = get_tsa04_df(tsa_df, event_info)
        event_info.tsa04_available = True
    else:
        event_info.tsa03_file = item["file_object"]
        tsa_df = get_tsa03_df(tsa_df, event_info)
        event_info.tsa03_available = True

    return tsa_df


def merge_dataframes(tsa04_df, tsa03_df, event_info):
    """
    Merge TSA04 and TSA03 DataFrames if both are available, otherwise adjust TSA04 DataFrame as
    needed.
    @param tsa04_df - The TSA04 DataFrame
    @param tsa03_df - The TSA03 DataFrame
    @param event_info - Information about the event
    @return Merged DataFrame if both TSA04 and TSA03 are available, otherwise adjusted TSA04
    DataFrame
    """
    if not event_info.tsa03_available:
        tsa04_df["Guests"] = ''
        return tsa04_df
    else:
        return pd.merge(tsa04_df, tsa03_df, on=["Date", "Location_ID"], how="left",
                        validate="many_to_many")


def add_additional_columns(input_df):
    """
    Add additional columns to the input dataframe for tracking departures, notes, transient
    occupied rooms, group occupied rooms, and permanent occupied rooms.
    @param input_df - the input dataframe
    @return The input dataframe with the additional columns added.
    """
    input_df["Departures"] = ''
    input_df["Notes"] = ''
    input_df["Transient_Occupied_Rooms"] = 0
    input_df["Group_Occupied_Rooms"] = 0
    input_df["Permanent_Occupied_Rooms"] = 0
    return input_df


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
