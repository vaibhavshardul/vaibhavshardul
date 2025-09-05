"""This module provides the functions which are used by other modules in
trancformation of each metrics"""

import json
from datetime import datetime, timedelta

import boto3
from charset_normalizer import detect
import pandas as pd
from bson import json_util

from Notifications.email_send import SendEmailNotification
from EtlServices.fpg_ing_mysql import FpgIngMySQL
from EtlServices.fpg_ops_mongo import FpgOpsMongo
from EtlServices.common_params import CommonParameters as params, CommonFunctions as cf
from EtlServices.etl_utilities import EtlUtilities as Utility

from model.app_constants import AppConstants as Constants
from model.event_info import EventInfo

from failSafePackage.fail_safe_validation import fail_safe_cls


s3 = boto3.client("s3")
sqs = boto3.client("sqs")

ops_db_mongo = FpgOpsMongo()
ing_db_mysql = FpgIngMySQL()
custom_exceptions = Utility.custom_exceptions

CAMBRIDGE_TSA02_TSA06_COMMON_HEADERS = ["BUSINESS_DATE", "RESORT", "NAME", "CI_DATE", "CI_TIME",
                "APP_USER", "LAST_NAME", "FIRST_NAME", "MEMBERSHIP_TYPE",
                "MEMBERSHIP_LEVEL", "CONFIRMATION_NO",]

def log_and_send_email(event_info, action, message, exception):
    """
    Log an error and send an email notification.
    """
    record = event_info.app_log.error(
        event_info.trace_id, event_info.span_id, action, message, exception    )
    SendEmailNotification(record).execute()

def log_info(event_info, action, message):
    """
    Log an error and send an email notification.
    """
    event_info.app_log.info(  event_info.trace_id, event_info.span_id, action, message    )

def fetch_number_of_files(event_info: EventInfo):
    """
    Fetch the number of files associated with the provided event information.

    Args:
        event_info (dict): Information about the event or extraction request.

    Returns:
        bool: True if file fetching and processing succeeded, False otherwise.
    """
    cambridge_fetch_number_of_files_action = "fetch_number_of_files"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    is_processing_success = True
    event_info.files_list = []

    try:
        for cambridge_req_id in event_info.extract_req_ids:
            Utility(event_info.app_log).update_extract_request(
                event_info, cambridge_req_id, Constants.EXTRACTION_PROCESSING_STARTED            )
            cambridge_file_info_dict = {}

            mongo_result = ops_db_mongo.find_one(
                Constants.DB_OPS_TBL_EXTRACT_REQUEST, {"req_id": cambridge_req_id}, {"_id": 0}
            )
            file_info = json_util.loads(json_util.dumps(mongo_result))
            log_info(event_info,
                cambridge_fetch_number_of_files_action,
                f"Extracted file events for '{tenant_id}' tenant_id and '"
                f"{location_code}' location is: '{json_util.dumps(file_info)}'",            )

            if file_info is None:
                raise ValueError(
                    f"Extract request information for '{cambridge_req_id}' req_id of '{tenant_id}' "
                    f"tenant_id and '{location_code}' location is not available in ops-db. "
                    f"Skipping the process."                )

            cambridge_file_info_dict["raw_file_name"] = file_info["req_original_event_obj"][
                "source_file_complete_path"
            ].split("/")[-1]
            event_info.raw_file_name = cambridge_file_info_dict["raw_file_name"]

            cambridge_file_info_dict["s3_bucket_name"] = file_info["file_bucket"]
            log_info(event_info,
                cambridge_fetch_number_of_files_action,
                f"Extract request - '{cambridge_req_id}' | Request file is available at '"
                f"{cambridge_file_info_dict['s3_bucket_name']}' s3 bucket",           )

            cambridge_file_info_dict["file_object"] = str(file_info["file_path"]) + str(
                file_info["file_name"]    )
            log_info(event_info,
                cambridge_fetch_number_of_files_action,
                f"Extract request - '{cambridge_req_id}' | Request file is available at '"
                f"{cambridge_file_info_dict['file_object']}' path",    )

            file_location_code = (
                cambridge_file_info_dict["file_object"].split("/")[-1].split("~")[1].strip()   )
            if str(file_location_code) != str(location_code):
                raise ValueError(
                    f"Extract request information for '{cambridge_req_id}' is invalid. Request '"
                    f"{location_code}' location is not matching with file '{file_location_code}' "
                    f"location for '{tenant_id}'. Skipping the process"  )

            log_info(event_info,
                cambridge_fetch_number_of_files_action,
                f"Extract request - '{cambridge_req_id}' | Request received for '{location_code}' "
                f"location and '{tenant_id}' tenant_id",    )

            cambridge_file_info_dict["metric_type"] = (
                file_info["file_name"].split(".")[0].split("~")[-3].strip())
            log_info(event_info,
                cambridge_fetch_number_of_files_action,
                f"Extract request - '{cambridge_req_id}' | Request received for '"
                f"{cambridge_file_info_dict['metric_type']}' metric type",)

            cambridge_file_info_dict["file_type"] = (
                file_info["file_name"].split(".")[0].split("~")[-1].strip())
            log_info(event_info,
                cambridge_fetch_number_of_files_action,
                f"Extract request - '{cambridge_req_id}' | Request received for '"
                f"{cambridge_file_info_dict['file_type']}' file type",)

            cambridge_file_info_dict["req_id"] = cambridge_req_id
            event_info.files_list.append(cambridge_file_info_dict)

        log_info(event_info,
            cambridge_fetch_number_of_files_action,
            f"Successfully extracted file events for '{tenant_id}' tenant_id and '"
            f"{location_code}' location of Cambridge PMS",)

    except custom_exceptions as cambridge_fetch_number_of_files_error:
        log_and_send_email(event_info,
            cambridge_fetch_number_of_files_action,
            f"Exception while extracting file events for '{tenant_id}' tenant_id "
            f"and '{location_code}' location. Request terminated for Cambridge",
            cambridge_fetch_number_of_files_error,)
        is_processing_success = False

    return is_processing_success


def get_metric_file_dict(event_info):
    """
    Constructs a dictionary of metric file information based on the given event information.
    """
    action = "get_metric_file_dict"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    is_processing_success = True

    try:
        log_info(event_info, action,
            f"Get the metric file dictionary for '{tenant_id}' tenant_id and '"
            f"{location_code}' location.",)

        metric_file_dict = {}
        for file in event_info.files_list:
            file_type = file["file_type"]
            metric_type = file["metric_type"]

            if metric_type not in metric_file_dict:
                metric_file_dict[metric_type] = []

            metric_file_dict[metric_type].append(file)

            if file_type == "TSA03":
                if "RM" not in metric_file_dict:
                    metric_file_dict["RM"] = []
                metric_file_dict["RM"].append(file)

        log_info(event_info, action,
            f"Successfully got the metric file dictionary for '{tenant_id}' tenant_id "
            f"and '{location_code}' location. Here is the dictionary: {metric_file_dict}",)

        event_info.metric_file_dict = metric_file_dict

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
            f"Exception while creating metric file dictionary for '{tenant_id}' "
            f"tenant_id and '{location_code}' location", e,)
        is_processing_success = False

    return is_processing_success


def extract_file_info(metric, event_info):
    """
    Extracts file information based on the given metric and event information.
    """
    action = "extract_file_info"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    is_processing_success = True

    try:
        log_info(event_info, action,
            f"Extract the file info for '{metric}' metric for '"
            f"{event_info.file_dict['file_object']}' file for '{tenant_id}' tenant_id "
            f"and '{location_code}' location.",)

        file_name = event_info.file_dict["file_object"].split("/")[-1]
        event_info.input_file_extension = file_name.split(".")[1].lower()
        file_name_split_values = file_name.split(".")[0].split("~")
        file_name_split_values = list(map(lambda x: x.strip(), file_name_split_values))

        (event_info.etl_type, event_info.file_location_code,  metric,file_date,
            file_type,) = file_name_split_values
        event_info.metric_date = datetime.strptime(
            file_date, "%d%m%Y").date() - timedelta(days=1)

        log_info(event_info,
            action,
            f"Requested daily date for Processing is : '{event_info.metric_date}' for '"
            f"{metric}' metric for '{event_info.file_dict['file_object']}' file for '"
            f"{tenant_id}' tenant_id and '{location_code}' location.",)

        input_file_name = "~".join([ event_info.etl_type, event_info.file_location_code,
                event_info.metric_type, file_date, file_type,  ])
        event_info.input_file_name = (
            input_file_name + "." + event_info.input_file_extension )
        event_info.app_log.input_file_name = (
            input_file_name + "." + event_info.input_file_extension )
        event_info.app_log.raw_file_name = event_info.file_dict["raw_file_name"]

        log_info(event_info, action,
            f"Successfully extracted the file info for '{event_info.input_file_name}' "
            f"file of '{metric}' metric for '{tenant_id}' tenant_id and '"
            f"{location_code}' location.",)

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
            f"Exception while extracting file info for '"
            f"{event_info.file_dict['file_object']}' file of '"
            f"{event_info.metric_type}' metric for '{tenant_id}' tenant_id and '"
            f"{location_code}' location. Skipping the process", e,)
        is_processing_success = False

    return is_processing_success


def get_tsa01_df(tsa01_df, event_info):
    """
    Retrieve the TSA01 dataframe for a specific file, tenant_id, and location_code.
    @param tsa01_df - the TSA01 dataframe
    @param event_info - information about the event
    @return The TSA01 dataframe and the count of df1.
    """
    cambridge_get_tsa01_df_action = "get_tsa01_df"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        log_info(event_info, cambridge_get_tsa01_df_action,
            f"Get the TSA01 dataframe for '{event_info.tsa01_file}' file for '"
            f"{tenant_id}' tenant_id and '{location_code}' location",)

        header_1 = tsa01_df.head(1).values[0]

        if "BUSINESS_DATE" in header_1:
            tsa01_df = tsa01_df.drop(0)

            if len(tsa01_df) == 0:
                log_info(event_info, cambridge_get_tsa01_df_action,
                    f"TSA01 dataframe is empty after removing headers for '"
                    f"{event_info.tsa01_file}' file for '{tenant_id}' tenant_id and '"
                    f"{location_code}' location",)
                event_info.tsa01_available = False
                return tsa01_df, 0
        else:
            header_1 = [
                "BUSINESS_DATE", "RESORT",  "NAME",  "RM_NO", "RM_TYPE", "PREV_RM_TYPE",
                "ADULTS",  "CHILDREN", "LAST_NAME", "FIRST_NAME",
                "CONFIRMATION_NO",  "NAME_ID", "CHKINDTE",  "CHKOUTDTE",
                "EXCHANGE_RATE", "CURRENCY_CODE",
                "RM_RATE", "USD_RATE",  "MARKET_CODE", "MARKET_DESC",
                "MARKET_GRP", "MARKET_GRP_DESC", "PACKAGES", "PKG_PRICE", "PAK_DESC", "QUANTITY",
                "OUTDATE",  "RESV_STATUS", "NATIONALITY", "RATE_CODE", "RATE_DESC",  "CFG_PRICE",
                "StaffID"]

            tsa01_df = tsa01_df.iloc[:, :19]

        header_dict_1 = params.tsa01_headers_dict
        tsa01_df.columns = cf.get_transformed_headers(header_dict_1, header_1)
        tsa01_df = tsa01_df.rename(columns={"Pkg_Price": "Product_Charge"})

        if tsa01_df.empty:
            log_info(event_info,  cambridge_get_tsa01_df_action,
                f"TSA01 dataframe is empty after removing the records with None values "
                f"for mandatory columns of '{event_info.tsa01_file}' file for '"
                f"{tenant_id}' tenant_id and '{location_code}' location",)
            event_info.tsa01_available = False
            return tsa01_df, 0

        initial_df_count = len(tsa01_df)
        tsa01_df["Daily_Date"] = tsa01_df["Daily_Date"].apply(
            fail_safe_cls(dayfirst=True, errors="ignore").daily_date_validation)

        log_info(event_info,cambridge_get_tsa01_df_action,
            "Successfully applied fail-safe condition on Daily Date for cambridge tsa01 file",
        )
        event_info.daily_date = tsa01_df.iloc[:1, :1].values[0][0]
        cambridge_tsa01_df = tsa01_df[tsa01_df.Daily_Date == event_info.daily_date]

        if cambridge_tsa01_df.empty:
            log_info(event_info, cambridge_get_tsa01_df_action,
                f"TSA01 dataframe is empty after removing the records whose business "
                f"date is not matching with Daily date of '{event_info.tsa01_file}' file "
                f"for '{tenant_id}' tenant_id and '{location_code}' location",)
            event_info.tsa01_available = False
            return cambridge_tsa01_df, 0

        if initial_df_count != len(cambridge_tsa01_df):
            log_info(event_info,
                cambridge_get_tsa01_df_action,
                f"Count of removed invalid rows from TSA01 file is : '"
                f"{initial_df_count - len(cambridge_tsa01_df)}'",)

        cambridge_tsa01_df = cambridge_tsa01_df.filter(
            items=[ "Confirmation_no", "Room_No","New_Room_Type","Original_Room_Type",
                "Daily_Date", "Arrival_Date", "Departure_Date",  "Product_Code",
                "Quantity", "Market_Segment", "Resv_Status", "Product_Charge",])

        cambridge_tsa01_df["Product_Charge"] = cambridge_tsa01_df["Product_Charge"].apply(
            fail_safe_cls().product_charge_validation)
        log_info(event_info, cambridge_get_tsa01_df_action,
            "Fail safe applied successfully on product charge",)

        cambridge_tsa01_df["Confirmation_no"] = cambridge_tsa01_df["Confirmation_no"].apply(
            fail_safe_cls().confirmation_no_validation )
        log_info(event_info, cambridge_get_tsa01_df_action,
            "Successfully applied fail-safe condition on Confirmation no",)

        if cambridge_tsa01_df.empty:
            log_info(event_info, cambridge_get_tsa01_df_action,
                f"Empty TSA01 dataframe after removing records whose daily date is not "
                f"between pkg_begin and pkg_end date for '{location_code}' location",)
            event_info.tsa01_available = False
            return cambridge_tsa01_df, 0

        log_info(event_info, cambridge_get_tsa01_df_action,
            f"Add columns to tsa01 for '{event_info.tsa01_file}' file for '{tenant_id}' "
            f"tenant_id and '{location_code}' location",)

        df1_count = len(cambridge_tsa01_df)
        log_info(event_info, cambridge_get_tsa01_df_action,
            f"Successfully got the TSA01 dataframe for '{event_info.tsa01_file}' file "
            f"for '{tenant_id}' tenant_id and '{location_code}' location",)

        return cambridge_tsa01_df, df1_count
    except custom_exceptions as e:
        log_and_send_email( event_info,cambridge_get_tsa01_df_action,
            f"Exception while getting the TSA01 dataframe for '"
            f"{event_info.metric_type}' metric of '{event_info.tsa01_file}' file "
            f"for '{tenant_id}' tenant_id and '{location_code}' location.", e, )
        event_info.tsa01_available = False
        return None, 0


def get_tsa02_df(cambridge_tsa02_df, event_info):
    """
    Retrieve the TSA02 dataframe for a specific file, tenant_id, and location_code.
    @param cambridge_tsa02_df - The TSA02 dataframe to be filtered
    @param event_info - Information about the event
    @return The filtered TSA02 dataframe.
    """
    cambridge_get_tsa02_df_action = "get_tsa02_df"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        log_info(event_info, cambridge_get_tsa02_df_action,
            f"Get the TSA02 dataframe for '{event_info.tsa02_file}' file for '"
            f"{tenant_id}' tenant_id and '{location_code}' location", )
        cambridge_tsa02_df = _process_tsa02_df(cambridge_tsa02_df, event_info,
                                         cambridge_get_tsa02_df_action)

        if cambridge_tsa02_df.empty:
            return cambridge_tsa02_df

        log_info(event_info,
            cambridge_get_tsa02_df_action,
            "Successfully applied fail-safe condition on Confirmation no",)

        cambridge_tsa02_df = cambridge_tsa02_df.filter(items=["Confirmation_no", "Employee_ID"])
        cambridge_tsa02_df.drop_duplicates(subset=["Confirmation_no"], inplace=True)

        log_info(event_info,
            cambridge_get_tsa02_df_action,
            f"Successfully got the TSA02 dataframe for '{event_info.tsa02_file}' file "
            f"for '{tenant_id}' tenant_id and '{location_code}' location",)

        return cambridge_tsa02_df

    except custom_exceptions as e:
        log_and_send_email(event_info, cambridge_get_tsa02_df_action,
            f"Exception while getting the TSA02 dataframe for '"
            f"{event_info.metric_type}' metric of '{event_info.tsa02_file}' file "
            f"for '{tenant_id}' tenant_id and '{location_code}' location.", e, )
        event_info.tsa02_available = False

        return None

def _process_tsa02_df(cambridge_tsa02_df, event_info, cambridge_get_tsa02_df_action):
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    cambridge_tsa02_df = cambridge_tsa02_df.iloc[:, :11]
    cambridge_tsa02_header_1 = cambridge_tsa02_df.head(1).values[0][:11]

    if "BUSINESS_DATE" in cambridge_tsa02_header_1:
        cambridge_tsa02_df = cambridge_tsa02_df.drop(0)

        if len(cambridge_tsa02_df) == 0:
            event_info.tsa02_available = False
            log_info(event_info, cambridge_get_tsa02_df_action,
            f"TSA02 dataframe is empty after removing headers for '{event_info.tsa02_file}'"
                     f" file for '{tenant_id}' tenant_id and '{location_code}' location", )
            return cambridge_tsa02_df
    else:
        cambridge_tsa02_header_1 = CAMBRIDGE_TSA02_TSA06_COMMON_HEADERS
        log_info(event_info, cambridge_get_tsa02_df_action,
        f"TSA02 dataframe (Rep File) does not have headers for '{event_info.tsa02_file}'"
                 f" file for '{tenant_id}' tenant_id and ' {location_code}' location", )

    cambridge_tsa02_header_dict_2 = {"CONFIRMATION_NO": "Confirmation_no",
                                     "APP_USER": "Employee_ID", }

    cambridge_tsa02_df.columns = cf.get_transformed_headers(cambridge_tsa02_header_dict_2,
                                                            cambridge_tsa02_header_1)

    tsa02_initial_df_count = len(cambridge_tsa02_df)
    cambridge_tsa02_df["BUSINESS_DATE"] = cambridge_tsa02_df["BUSINESS_DATE"].apply(
        fail_safe_cls(dayfirst=True, errors="ignore").daily_date_validation)
    log_info(event_info, cambridge_get_tsa02_df_action,
             "Successfully applied fail-safe condition on Daily Date", )

    event_info.daily_date = cambridge_tsa02_df.iloc[:1, :1].values[0][0]
    cambridge_tsa02_df = cambridge_tsa02_df[
        cambridge_tsa02_df["BUSINESS_DATE"] == event_info.daily_date]
    log_info(event_info, cambridge_get_tsa02_df_action,
            f"TSA02 dataframe daily date is '{event_info.daily_date}' for '"
       f"{event_info.tsa02_file}' file for '{tenant_id}' tenant_id and '{location_code}' location")

    if cambridge_tsa02_df.empty:
        log_info(event_info, cambridge_get_tsa02_df_action,
                 f"TSA02 dataframe is empty after removing the records whose business "
                 f"date is not matching with Daily date of '{event_info.tsa02_file}' file "
                 f"for '{tenant_id}' tenant_id and '{location_code}' location", )
        event_info.tsa02_available = False
        return cambridge_tsa02_df

    if tsa02_initial_df_count != len(cambridge_tsa02_df):
        log_info(event_info, cambridge_get_tsa02_df_action,
                 f"count of removed invalid rows "
                 f"is : '{tsa02_initial_df_count - len(cambridge_tsa02_df)}'", )

    cambridge_tsa02_df["Confirmation_no"] = cambridge_tsa02_df["Confirmation_no"].apply(
        fail_safe_cls().confirmation_no_validation)
    return cambridge_tsa02_df


def get_tsa04_df(tsa04_df, event_info):
    """
    Retrieve the TSA04 dataframe based on the event information provided. If an exception occurs,
    log the error and send an email notification.
    @param tsa04_df - the TSA04 dataframe
    @param event_info - information about the event
    @return the TSA04 dataframe
    """
    cambridge_get_tsa04_df_action = "get_tsa04_df"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        log_info(event_info, cambridge_get_tsa04_df_action,
            f"Get the TSA04 dataframe for '{event_info.tsa04_file}' file for '"
            f"{tenant_id}' tenant_id and '{location_code}' location",)

        cambridge_tsa04_header_1 = tsa04_df.head(1).values[0]

        if "BUSINESS_DATE" in cambridge_tsa04_header_1:
            tsa04_df = tsa04_df.drop(0)

            if len(tsa04_df) == 0:
                event_info.tsa04_available = False
                log_info(event_info, cambridge_get_tsa04_df_action,
                    f"TSA04 dataframe is empty after removing headers for '"
                    f"{event_info.tsa04_file}' file for '{tenant_id}' tenant_id and '"
                    f"{location_code}' location",)
                return tsa04_df
        else:
            # Find index of "DAYUSE_ROOM" and insert before it
            cambridge_tsa04_header_1 = params.tsa04_headers[:-1]
            dayuse_index = cambridge_tsa04_header_1.index("DAYUSE_ROOM")
            cambridge_tsa04_header_1.insert(dayuse_index, "HOUSE_USE_ROOM")

            log_info(event_info,
                cambridge_get_tsa04_df_action,
                f"TSA04 dataframe (Rep File) does not have headers for '"
                f"{event_info.tsa04_file}' file for '{tenant_id}' tenant_id and '"
                f"{location_code}' location",)
            tsa04_df = tsa04_df.iloc[:, :18]

        header_dict_1 = params.tsa04_header_dict

        tsa04_df.columns = cf.get_transformed_headers(header_dict_1, cambridge_tsa04_header_1)

        tsa04_df["Date"] = tsa04_df["Date"].apply(
            fail_safe_cls(dayfirst=True, errors="coerce").daily_date_validation)
        log_info(event_info, cambridge_get_tsa04_df_action,
            "Successfully applied Failsafe on 'Date' in TSA04 dataframe",)

        event_info.daily_date = tsa04_df.iloc[:1, :1].values[0][0]
        log_info(event_info, cambridge_get_tsa04_df_action,
            f"TSA01 dataframe daily date is '{event_info.daily_date}' for '"
            f"{event_info.tsa04_file}' file for '{tenant_id}' tenant_id and '"
            f"{location_code}' location", )

        tsa04_df = tsa04_df[tsa04_df["Date"] == event_info.daily_date]

        if tsa04_df.empty:
            event_info.tsa04_available = False
            log_info(event_info, cambridge_get_tsa04_df_action,
                f"TSA04 dataframe is empty after removing the records whose business "
                f"date is not matching with Daily date of '{event_info.tsa04_file}' file "
                f"for '{tenant_id}' tenant_id and '{location_code}' location",)
            return tsa04_df

        tsa04_df = calculate_values_for_tsa04(tsa04_df)
        log_info(event_info,  cambridge_get_tsa04_df_action,
            f"Fail-safe applied successfully on room revenue inside "
            f"calculate_values_for_tsa04 function, and Successfully got the TSA04 "
            f"dataframe for '{event_info.tsa04_file}' file for '{tenant_id}' tenant_id "
            f"and '{location_code}' location", )

        return tsa04_df

    except custom_exceptions as e:
        log_and_send_email(event_info, cambridge_get_tsa04_df_action,
            f"Exception while getting the TSA04 dataframe for '"
            f"{event_info.metric_type}' metric of '{event_info.tsa04_file}' file "
            f"for '{tenant_id}' tenant_id and '{location_code}' location.", e, )
        event_info.tsa04_available = False
        return None


def calculate_values_for_tsa04(tsa04_df):
    """
    Calculate additional values for the TSA04 dataframe and return the updated dataframe.
    @param tsa04_df - the TSA04 dataframe to be updated
    @return The updated TSA04 dataframe with additional calculated values.
    """
    action = "calculate_values_for_tsa04"
    try:
        tsa04_df["Room_Revenue"] = tsa04_df["Room_Revenue"].apply(
            fail_safe_cls().room_revenue_validation_without_round)
        other_columns_list = [
            "Rooms_Occupied", "Vacant_Rooms", "Out_of_Order_Rooms",
            "Out_of_Service_Rooms", "Complimentary_Rooms", "House_use_Rooms", "Arrivals"]

        numeric_value_validation = fail_safe_cls.room_revenue_validation_without_round
        for column in other_columns_list:
            tsa04_df[column] = (
                tsa04_df[column].fillna(0).apply(numeric_value_validation).astype(int) )

        group_by_columns =  other_columns_list.copy()
        group_by_columns.append("Room_Revenue")
        tsa04_df = (tsa04_df.groupby(["Date", "Location_ID"])[group_by_columns]
            .agg("sum").reset_index())

        tsa04_df["Rooms_Available"] = (tsa04_df["Rooms_Occupied"] + tsa04_df["Vacant_Rooms"]
            - tsa04_df["Out_of_Order_Rooms"] - tsa04_df["Out_of_Service_Rooms"]
            - tsa04_df["Complimentary_Rooms"]  - tsa04_df["House_use_Rooms"] )

        tsa04_df = tsa04_df[params.tsa04_required_headers]

        tsa04_df["Room_Revenue"] = tsa04_df["Room_Revenue"].apply(lambda x: round(x, 2))
        return tsa04_df
    except custom_exceptions as e:
        log_and_send_email( event_info=EventInfo,  action=action,
            message=f"Exception while calculating tsa04 columns values. Reason {e}",
            exception=e, )
        return None


def get_tsa03_df(cambridge_tsa03_df, event_info):
    """
    Retrieve and process the TSA03 dataframe based on event information.
    @param tsa03_df - The TSA03 dataframe to be processed.
    @param event_info - Information about the event.
    @return The processed TSA03 dataframe.
    """
    cambridge_get_tsa03_df_action = "get_tsa03_df"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        log_info(event_info,cambridge_get_tsa03_df_action,
            f"Get the TSA03 dataframe for '{event_info.tsa03_file}' file for '"
            f"{tenant_id}' tenant_id and '{location_code}' location", )

        cambridge_tsa03_df = _process_tsa03_df(cambridge_tsa03_df, event_info,
                                         cambridge_get_tsa03_df_action)

        if cambridge_tsa03_df.empty:
            return cambridge_tsa03_df

        cambridge_tsa03_df["Guests"] = cambridge_tsa03_df["Guests"].fillna(0).astype(int)
        cambridge_tsa03_df = (cambridge_tsa03_df.groupby(["Date", "Location_ID"])[["Guests"]]
                              .agg("sum").reset_index())
        cambridge_tsa03_df["Date"] = cambridge_tsa03_df["Date"].apply(
            fail_safe_cls(errors="coerce").daily_date_validation)
        log_info(event_info, cambridge_get_tsa03_df_action,
            "Successfully applied Failsafe on 'Date' in TSA03 dataframe",        )
        log_info(event_info, cambridge_get_tsa03_df_action,
            f"Successfully got the TSA03 dataframe for '{event_info.tsa03_file}' file "
            f"for '{tenant_id}' tenant_id and '{location_code}' location",        )

        return cambridge_tsa03_df

    except custom_exceptions as e:
        log_and_send_email( event_info, cambridge_get_tsa03_df_action,
            f"Exception while getting the TSA03 dataframe for '"
            f"{event_info.metric_type}' metric of '{event_info.tsa03_file}' file "
            f"for '{tenant_id}' tenant_id and '{location_code}' location.", e,        )
        event_info.tsa03_available = False

        return None


def _process_tsa03_df(cambridge_tsa03_df, event_info, cambridge_get_tsa03_df_action):
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code
    cambridge_tsa03_header_1 = cambridge_tsa03_df.head(1).values[0]

    if "BUSINESS_DATE" in cambridge_tsa03_header_1:
        cambridge_tsa03_df = cambridge_tsa03_df.drop(0)
        if len(cambridge_tsa03_df) == 0:
            event_info.tsa03_available = False
            log_info(event_info, cambridge_get_tsa03_df_action,
                     f"TSA03 dataframe is empty after removing headers for '"
                     f"{event_info.tsa03_file}' file for '{tenant_id}' tenant_id and '"
                     f"{location_code}' location", )
            return cambridge_tsa03_df
    else:
        cambridge_tsa03_header_1 = params.tsa03_headers

        log_info(event_info, cambridge_get_tsa03_df_action,
                 f"TSA03 dataframe (Rep File) does not have headers for '"
                 f"{event_info.tsa03_file}' file for '{tenant_id}' tenant_id and '"
                 f"{location_code}' location", )
        cambridge_tsa03_df = cambridge_tsa03_df.iloc[:, :11]

    header_dict_2 = params.tsa03_header_dict
    cambridge_tsa03_df.columns = cf.get_transformed_headers(header_dict_2,
                                                            cambridge_tsa03_header_1)

    initial_df_count = len(cambridge_tsa03_df)
    cambridge_tsa03_df["Date"] = cambridge_tsa03_df["Date"].apply(
        fail_safe_cls(dayfirst=True, errors="coerce").daily_date_validation)
    log_info(event_info, cambridge_get_tsa03_df_action,
             "Successfully applied Failsafe on 'Date' in TSA03 dataframe", )

    event_info.daily_date = cambridge_tsa03_df.iloc[:1, :1].values[0][0]
    cambridge_tsa03_df = cambridge_tsa03_df[cambridge_tsa03_df["Date"] == event_info.daily_date]
    log_info(event_info, cambridge_get_tsa03_df_action,
             f"TSA03 dataframe daily date is '{event_info.daily_date}' for '"
             f"{event_info.tsa03_file}' file for '{tenant_id}' tenant_id and '"
             f"{location_code}' location", )

    if cambridge_tsa03_df.empty:
        event_info.tsa03_available = False
        log_info(event_info, cambridge_get_tsa03_df_action,
                 f"TSA03 dataframe is empty after removing the records whose business "
                 f"date is not matching with Daily date of '{event_info.tsa03_file}' file "
                 f"for '{tenant_id}' tenant_id and '{location_code}' location", )
        return cambridge_tsa03_df

    if initial_df_count != len(cambridge_tsa03_df):
        log_info(event_info, cambridge_get_tsa03_df_action,
                 f"Count of removed invalid rows is: '"
                 f"{str(initial_df_count - len(cambridge_tsa03_df))}'", )

    return cambridge_tsa03_df


def get_tsa06_df(tsa06_df, event_info):
    """
    Retrieve the TSA06 dataframe based on the event information provided.
    @param tsa06_df - the TSA06 dataframe
    @param event_info - information about the event
    @return the TSA06 dataframe or handle exceptions and send email notifications
    """
    action = "get_tsa06_df"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        log_info(event_info, action,
            f"Get the TSA06 dataframe for '{event_info.input_file_name}' file for '"
            f"{tenant_id}' tenant_id and '{location_code}' location",        )

        header_1 = tsa06_df.head(1).values[0]
        first_value = tsa06_df.iloc[:1, :1].values[0][0]
        if first_value == 0:
            tsa06_df.drop(tsa06_df.columns[0], axis=1, inplace=True)

        if "BUSINESS_DATE" in header_1 or (
            event_info.location_code in tsa06_df.columns and not event_info.drop_headers        ):
            tsa06_df = tsa06_df.iloc[:, : len(header_1)]
            tsa06_df.columns = header_1

        if "BUSINESS_DATE" in header_1:
            tsa06_df = tsa06_df.drop(0)
            if len(tsa06_df) == 0:
                log_info(event_info,action,
                    f"TSA06 dataframe is empty after removing headers for '"
                    f"{event_info.input_file_name}' file for '{tenant_id}' tenant_id and "
                    f"'{location_code}' location",                )
                return tsa06_df
        else:
            header_1 = (CAMBRIDGE_TSA02_TSA06_COMMON_HEADERS  +
                        [
                        "CHKINDTE", "END_DATE", "RESV_STATUS", "CHKOUTDTE", "ROOM", "CREATE_DATE",
                        "BOOKED_ROOM_CATEGORY_LABEL", "ADULTS", "CHILDREN", "MARKET_CODE", "MARKET_DESC",
                        "PRODUCTS", "RATE_CODE", "RATE_DESC", "RATE_VALUE", "CFG_PRICE", "SOURCE_CODE",
                        "SOURCE_DESC", "NATIONALITY", "DISCOUNT_AMT", "DISCOUNT_PRCNT",
                        "DISCOUNT_REASON_CODE", "SPECIAL_REQUESTS" ] )

        header_dict_1 = params.tsa06_headers_dict

        tsa06_df.columns = cf.get_transformed_headers(header_dict_1, header_1)

        initial_df_count = len(tsa06_df)
        tsa06_df["Date"] = tsa06_df["Date"].apply(
            fail_safe_cls(dayfirst=True, errors="coerce").daily_date_validation        )
        log_info(event_info, action,
            "Successfully applied Failsafe on 'Date' in TSA06 dataframe",        )

        event_info.daily_date = tsa06_df.iloc[:1, :1].values[0][0]
        tsa06_df = tsa06_df[tsa06_df["Date"] == event_info.daily_date]
        log_info(event_info, action,
            f"TSA06 dataframe daily date is '{event_info.daily_date}' for '"
            f"{event_info.input_file_name}' file for '{tenant_id}' tenant_id and '"
            f"{location_code}' location",        )

        if tsa06_df.empty:
            log_info(event_info, action,
                f"TSA06 dataframe is empty after removing the records whose business "
                f"date is not matching with Daily date of '{event_info.input_file_name}' "
                f"file for '{tenant_id}' tenant_id and '{location_code}' location",            )
            return tsa06_df

        if initial_df_count != len(tsa06_df):
            log_info(event_info, action,
                f"Count of removed invalid rows is: '"
                f"{str(initial_df_count - len(tsa06_df))}'",            )

        tsa06_df = calculate_values_for_tsa06(tsa06_df, event_info)

        log_info(event_info, action,
            f"Successfully got the TSA06 dataframe and count is: '{len(tsa06_df)}' for "
            f"'{event_info.input_file_name}' file for '{tenant_id}' tenant_id and '"
            f"{location_code}' location",        )

        return tsa06_df

    except custom_exceptions as e:
        log_and_send_email(event_info,action,
            f"Exception while getting the TSA06 dataframe for '"
            f"{event_info.metric_type}' metric of '{event_info.input_file_name}' "
            f"file for '{tenant_id}' tenant_id and '{location_code}' location.", e,        )

        return None


def calculate_values_for_tsa06(tsa06_df, event_info):
    """
    Calculate additional values for TSA06 dataframe based on event information.
    @param tsa06_df - TSA06 dataframe containing specific columns.
    @param event_info - Information about the event such as event_info.trace_id and
    event_info.span_id.
    @return Updated TSA06 dataframe with additional columns for Employee_Last_Name and
    Employee_Email_Address.
    """
    action = "calculate_values_for_tsa06"

    try:
        tsa06_df = tsa06_df[ [ "Date","CHKINDTE", "RESV_STATUS", "Confirmation_no", "Employee_ID",
                "Location_ID", "ROOM", ] ]
        tsa06_df["Date"] = tsa06_df["Date"].apply(
            fail_safe_cls(errors="coerce").daily_date_validation        )
        log_info(event_info, action,
            "Successfully applied Failsafe on 'Date' in TSA06 dataframe in "
            "calculate_values_for_tsa06 function.",        )

        tsa06_df["CHKINDTE"] = tsa06_df["CHKINDTE"].apply(
            fail_safe_cls(dayfirst=True, errors="coerce").daily_date_validation        )
        log_info(event_info, action,
            "Successfully applied Failsafe on 'CHKINDTE' in TSA06 dataframe in "
            "calculate_values_for_tsa06 function.",        )

        max_dt = tsa06_df["Date"].max()
        tsa06_df = tsa06_df[tsa06_df["Date"] == max_dt]
        tsa06_df = tsa06_df[tsa06_df["CHKINDTE"] == max_dt]
        tsa06_df["RESV_STATUS"] = tsa06_df["RESV_STATUS"].fillna("").str.strip()
        tsa06_df = tsa06_df[tsa06_df["RESV_STATUS"] == "In House"]

        log_info(event_info, action,
            f"The number of records in input file after filtered on CHKINDTE = "
            f"Business_Date is: {len(tsa06_df)}",        )

        df2 = tsa06_df.groupby(["Employee_ID", "Date", "Location_ID"])[
            ["Confirmation_no", "ROOM"]].nunique()
        df2.reset_index(inplace=True)

        other_columns_list = ["Confirmation_no", "ROOM"]
        for column in other_columns_list:
            df2[column] = df2[column].fillna(0).astype(float).astype(int)

        df2.rename(   columns={"Confirmation_no": "Arrivals", "ROOM": "Room_Nights_Sold"},
            inplace=True,       )
        df2["Employee_ID"].replace(
            to_replace=r"[@,\s](.*)", value=r"", regex=True, inplace=True        )

        df2["Notes"] = ""
        df2["Employee_Fist_Name"] = ""
        df2["Employee_Last_Name"] = ""
        df2["Employee_Email_Address"] = ""

        log_info(event_info,
            action, f"The number of records in the output file is: {len(df2)}",        )
        return df2
    except custom_exceptions as e:
        log_and_send_email( event_info, action,
            "Exception while calculating tsa06 columns values. Reason ",    e,    )
        return None


def get_rm_df(rm_df, event_info):
    """
    Retrieve the room metric dataframe based on event information.
    @param rm_df - the room metric dataframe
    @param event_info - information about the event
    @return The room metric dataframe.
    """
    cambridge_get_rm_df_action = "get_rm_df"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        log_info(event_info,
            cambridge_get_rm_df_action,
            f"Get the room metric dataframe for '{event_info.input_file_name}' file for "
            f"'{tenant_id}' tenant_id and '{location_code}' location",        )
        cambridge_rm_header_1 = rm_df.head(1).values[0]

        if "BUSINESS_DATE" in cambridge_rm_header_1:
            rm_df = rm_df.drop(0)

            if len(rm_df) == 0:
                log_info(event_info,
                    cambridge_get_rm_df_action,
                    f"TSA03 dataframe is empty after removing headers for '"
                    f"{event_info.input_file_name}' file for '{event_info.metric_type}' "
                    f"metric for '{tenant_id}' tenant_id and '{location_code}' location",                )
                return rm_df
        else:
            cambridge_rm_header_1 = params.tsa03_headers

            log_info(event_info,
                cambridge_get_rm_df_action,
                f"RM dataframe (Rep File) does not have headers for '"
                f"{event_info.input_file_name}' file for '{event_info.metric_type}' "
                f"metric for tenant_id and '{location_code}' location for cambridge PMS",            )
            rm_df = rm_df.iloc[:, :18]

        cambridge_rm_header_dict_1 = {"BUSINESS_DATE": "Date",  "RESORT": "Location_ID",
            "ROOM_TYPE": "Room_Type", "NO_OF_DEFINITE_ROOM": "Rooms_Occupied",
            "OO_ROOM": "Out_of_Order_Room",   }
        cambridge_transformed_header_1 = [
            cambridge_rm_header_dict_1.get(str(h).strip(), str(h).strip())
            for h in cambridge_rm_header_1 ]
        rm_df.columns = cambridge_transformed_header_1

        initial_df_count = len(rm_df)
        rm_df["Date"] = rm_df["Date"].apply(
            fail_safe_cls(dayfirst=True, errors="coerce").daily_date_validation      )
        log_info(event_info, cambridge_get_rm_df_action,
            "Successfully applied Failsafe on 'Date' in RM dataframe in get_rm_df "
            "function.",     )

        event_info.daily_date = rm_df.iloc[:1, :1].values[0][0]
        rm_df = rm_df[rm_df["Date"] == event_info.daily_date]
        log_info(event_info,  cambridge_get_rm_df_action,
            f"rmdf dataframe daily date is '{event_info.daily_date}' for '"
            f"{event_info.input_file_name}' file for '{tenant_id}' tenant_id and '"
            f"{location_code}' location", )

        if rm_df.empty:
            log_info(event_info,
                cambridge_get_rm_df_action,
                f"TSA03 dataframe is empty after removing the records whose business "
                f"date is not matching with Daily date of '{event_info.input_file_name}' "
                f"file for '{event_info.metric_type}' metric and '{tenant_id}' tenant_id "
                f"and '{location_code}' location",)
            return rm_df

        if initial_df_count != len(rm_df):
            log_info(event_info,
                cambridge_get_rm_df_action,
                f"Count of removed invalid rows is: '"
                f"{str(initial_df_count - len(rm_df))}'",   )

        rm_df = calculate_values_for_rm(rm_df, event_info)
        log_info(event_info, cambridge_get_rm_df_action,
            f"Successfully got the room_metric dataframe and count is: '{len(rm_df)}' "
            f"for '{str(event_info.input_file_name)}' file for '{tenant_id}' tenant_id "
            f"and '{location_code}' location",)

        return rm_df

    except custom_exceptions as e:
        log_and_send_email( event_info, cambridge_get_rm_df_action,
            f"Exception while getting rm_df for '{event_info.metric_type}' metric "
            f"of '{event_info.input_file_name}' file for '{tenant_id}' tenant_id "
            f"and '{location_code}' location.", e,)
        return None


def calculate_values_for_rm(cambridge_rm_df, event_info):
    """
    Calculate additional values for the room dataframe based on event information.
    @param rm_df - the room dataframe
    @param event_info - information about the event
    @return the updated room dataframe with additional calculated values
    """
    cambridge_calculate_values_for_rm_action = "cambridge_calculate_values_for_rm"
    try:
        other_columns_list = ["Rooms_Occupied", "Out_of_Order_Room", "EXISTING_ROOM"]
        numeric_value_validation = fail_safe_cls.room_revenue_validation_without_round
        for column in other_columns_list:
            cambridge_rm_df[column] = (
                cambridge_rm_df[column].fillna(0).apply(numeric_value_validation).astype(int))

        cambridge_rm_df = (
            cambridge_rm_df.groupby(["Date", "Location_ID", "Room_Type"])
            .agg({   "Rooms_Occupied": "sum",  "Out_of_Order_Room": "sum",
                "EXISTING_ROOM": "sum"}).reset_index())
        cambridge_rm_df.rename(columns={"EXISTING_ROOM": "Total_Rooms"}, inplace=True)
        cambridge_rm_df["Vacant_Room"] = (cambridge_rm_df["Total_Rooms"] -
                                          cambridge_rm_df["Rooms_Occupied"])
        cambridge_rm_df = cambridge_rm_df[["Date", "Room_Type", "Rooms_Occupied",
                "Location_ID", "Vacant_Room", "Out_of_Order_Room", ] ]

        cambridge_rm_df["Notes"] = ""
        cambridge_rm_df["Date"] = cambridge_rm_df["Date"].apply(
            fail_safe_cls(errors="coerce").daily_date_validation       )
        log_info(event_info,
            cambridge_calculate_values_for_rm_action,
            "Successfully applied Failsafe on 'Date' in RM dataframe in "
            "calculate_values_for_rm function.",        )

        return cambridge_rm_df
    except custom_exceptions as e:
        log_and_send_email( event_info, cambridge_calculate_values_for_rm_action,
            "Exception while calculating room metric df columns values. Reason  ",
            e,   )
        return None


def check_original_file_name(event_info, metric):
    """
    Check the original file name for a given event information.
    @param event_info - Information about the event
    @param metric - Information about the metric
    @return missing_file_list - List of missing file
    """
    action = "check_original_file_name"

    try:
        missing_file_list = []
        for key, value in event_info.metric_file_dict.items():
            if key == metric:
                for file_info in value:
                    original_file_name = get_original_file_name(event_info, file_info)
                    missing_file_list.append(original_file_name)

        missing_file_list = ",".join(missing_file_list)
        return missing_file_list
    except custom_exceptions as e:
        log_and_send_email( event_info, action,
            f"Exception while reading original file name for "
            f"'{event_info.raw_file_name}' file for '"
            f"{event_info.tenant_id}' tenant_id and '{event_info.location_code}' "
            f"location. Skipping "
            f"{metric} transformation",  e, )
        return None


def get_original_file_name(event_info, file_info):
    """
    Retrieve the original file name based on the trace ID and file information provided.
    @param event_info - The unique identifier for the trace
    @param file_info - Information about the file
    @return The original file name
    """
    raw_file_name = file_info["raw_file_name"]
    if raw_file_name.startswith("0_"):
        select_query_original_file = f"""
            SELECT DISTINCT mp.orignal_file_name 
            FROM missing_pms_temp_file AS mp 
            WHERE mp.raw_bucket_file_name = '{raw_file_name}'
        """
        result = ing_db_mysql.query(event_info, select_query_original_file)
        if result:
            return result[0][0] if result[0][0] else ""
        return ""

    return raw_file_name.split()[-1].split("_", 1)[-1]
