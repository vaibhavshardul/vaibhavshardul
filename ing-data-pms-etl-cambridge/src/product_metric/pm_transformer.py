"""Transformation logic for the Product metrics"""
import pandas as pd
from EtlServices.etl_utilities import EtlUtilities as Utility
from EtlServices.fpg_ing_mysql import FpgIngMySQL
from EtlServices.fpg_ops_mongo import FpgOpsMongo
from Notifications.email_send import SendEmailNotification
from failSafePackage.fail_safe_validation import fail_safe_cls
from pandasql import sqldf
from action.event_analyzer import get_tsa01_df, get_tsa02_df, \
    check_original_file_name
from model.app_constants import AppConstants as Constants

ops_db_mongo = FpgOpsMongo()
ing_db_mysql = FpgIngMySQL()
custom_exceptions = Utility.custom_exceptions


def pm_transformer(event_info):
    """
    Transform the event information for the performance metrics.
    @param event_info - the information about the event
    @return status - True if successful, False otherwise.
    """
    action = "pm_transformer"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Processing transformation for '{event_info.metric_type}' metric for '"
                     f"{tenant_id}' tenant_id and '{location_code}' location.")

        event_info.raw_file_name = check_original_file_name(event_info, "PM")

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Original file name successfully checked for '{event_info.metric_type}' "
                     f"metric for '{event_info.input_file_name}' file has '"
                     f"{event_info.raw_file_name}' raw filename of '{tenant_id}' tenant_id and '"
                     f"{location_code}' location. ")

        event_info.output_metric = "PRODUCT_METRIC"
        event_info.entity_type = 5

        event_info.import_id = Utility(event_info.app_log).insert_log_table(event_info,
                                                        Constants.DB_ING_TBL_IMPORTED_FILE_LOG)
        if event_info.import_id is None:
            return False

        output_df = process_pm(event_info)
        if output_df is None:
            return False
        elif output_df.empty:
            status = Utility(event_info.app_log).create_no_upsell_df(event_info)
        else:
            status = Utility(event_info.app_log).upload_file_s3(output_df, event_info)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Successfully completed transformation for '{tenant_id}' tenant_id and '"
                     f"{location_code}' location.")

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while transforming '{event_info.metric_type}' metric for "
                           f"'{tenant_id}' tenant_id for '{location_code}' location.",
                           e)
        status = False

    return status


def process_pm(event_info):
    """
    Process performance metrics based on event information and handle exceptions by logging and
    sending email notifications.
    @param event_info - Information about the event
    @return None
    """
    action = "process_pm"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Processing '{event_info.metric_type}' metric for '{tenant_id}' tenant_id "
                     f"and '{location_code}' location.")

        tsa01_df, tsa01_df_count, tsa02_df, tsa02_df_count = process_tsa_files(event_info)

        if not event_info.tsa01_available:
            return pd.DataFrame()

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Input df count before getting employee ID's is: '{tsa01_df_count}' and "
                     f"TSA02 is {tsa02_df_count}")

        input_df = merge_tsa_files(event_info, tsa01_df, tsa02_df)
        input_df_count = len(input_df)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Input df count after getting employee ID's is: '{input_df_count}'")

        if tsa01_df_count != input_df_count:
            raise ValueError(
                f"Some confirmation numbers have multiple Employee IDs in TSA02 file '"
                f"{event_info.tsa02_file}' for '{tenant_id}' tenant_id and '{location_code}' "
                f"location")

        input_df['Notes'] = ""
        input_df['Upgrade_Amount'] = ""
        input_df['Location_ID'] = location_code

        input_df["Product_Code"] = input_df["Product_Code"].astype(str).str.strip()

        input_df = apply_fail_safe_conditions_charge_days(event_info, input_df)

        input_df["Pkg_Code"] = input_df["Product_Code"].str.replace(r"[^a-zA-Z]", "", regex=True)

        product_mapping_df, product_mapping_other_revenue_df = create_products_df(event_info)
        if product_mapping_df is None:
            return None

        product_category_mapping_df_query = "SELECT Distinct Product_Code, Product_Category, " \
                                            "Location_ID FROM product_mapping_df"
        product_category_mapping_df = sqldf(product_category_mapping_df_query, locals())
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"input_df_count_with_productid {len(product_category_mapping_df)}")
        input_with_category_df_query = "SELECT i.*, p.Product_Category FROM input_df i LEFT JOIN " \
                                       "product_category_mapping_df p ON i.Pkg_Code = " \
                                       "p.Product_Code "
        input_with_category_df = sqldf(input_with_category_df_query, locals())
        input_with_category_df_count = len(input_with_category_df)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"input_df_count_with_productid {input_with_category_df_count}")

        if input_with_category_df_count != input_df_count:
            raise ValueError(
                "Failed: The number of rows in the input dataframe has changed after adding "
                "product category.")

        unrecognized_product_codes_df = unrecognized_product_code(event_info,
                                                                  input_with_category_df)
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"unrecognized_product_codes_df {len(unrecognized_product_codes_df)}")
        input_room_upsell_product_df = create_room_upsell(event_info, input_with_category_df,
                                                          product_mapping_df)
        if input_room_upsell_product_df is None:
            return None

        input_non_room_upsell_product_all_df = create_other_revenue(event_info,
                                                                    input_with_category_df,
                                                                product_mapping_other_revenue_df)
        if input_non_room_upsell_product_all_df is None:
            return None

        input_non_room_upsell_product = remove_non_room_upsell_records(event_info,
                                                            input_non_room_upsell_product_all_df)
        if input_non_room_upsell_product is None:
            return None

        union_query = "SELECT * FROM input_room_upsell_product_df UNION ALL SELECT * from " \
                      "input_non_room_upsell_product"
        df5 = sqldf(union_query, locals())
        output_df = df5.drop(['Pkg_Code', 'Resv_Status'], axis=1)
        output_df_count = len(output_df)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"The number of records in the output file is: {output_df_count}")

        if output_df is None:
            return None

        if len(output_df) == 0:
            return pd.DataFrame()

        output_df = apply_fail_safe_conditions_date_and_mapping(event_info, output_df)

        output_df = output_df[["Confirmation_no", "Room_No", "New_Room_Type", "Original_Room_Type",
                               "Daily_Date", "Arrival_Date", "Departure_Date", "Product_Code",
                               "Product_Charge", "Quantity", "Market_Segment", "Employee_ID",
                               "Notes", "Upgrade_Amount", "Location_ID", "Charge_Days",
                               "Product_Category",
                               "Product"]]

        return output_df

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while processing '{event_info.metric_type}' transformation "
                           f"for '{tenant_id}' tenant_id and '{location_code}' location",
                           e)
        return None


def process_tsa_files(event_info):
    """
    Process TSA files from event information and update the TSA dataframes accordingly.
    @param event_info - Information about the event and files
    @return None
    """
    tsa01_df = None
    tsa02_df = None
    tsa01_df_count = 0
    tsa02_df_count = 0

    for item in event_info.file_dict_list:
        file_type = item["file_type"]
        if file_type == "TSA01":
            event_info.tsa01_available = True
            tsa01_df, tsa01_df_count = Utility(event_info.app_log).read_s3_file_common(event_info,
                                                item, delimiter="\t", use_global_s3=True,
                                                        no_header_row=True, quoting_required=True)
            event_info.tsa01_file = item['file_object']
            if tsa01_df is not None:
                tsa01_df, tsa01_df_count = get_tsa01_df(tsa01_df, event_info)
        else:
            event_info.tsa02_available = True
            tsa02_df, tsa02_df_count = Utility(event_info.app_log).read_s3_file_common(event_info,
                                                item, delimiter="\t", use_global_s3=True,
                                                        no_header_row=True, quoting_required=True)
            event_info.tsa02_file = item['file_object']
            if tsa02_df is not None and not tsa02_df.empty:
                tsa02_df = get_tsa02_df(tsa02_df, event_info)
    return tsa01_df, tsa01_df_count, tsa02_df, tsa02_df_count


def merge_tsa_files(event_info, tsa01_df, tsa02_df):
    """
    Merge two TSA (Transportation Security Administration) files based on the confirmation
    number. If TSA02 data is not available, add an "Employee_ID" column to TSA01 data and return
    the updated TSA01 data. If TSA02 data is available, merge TSA01 and TSA02 data on the
    confirmation number using a left join.
    @param event_info - Information about the event and TSA data availability.
    @param tsa01_df - TSA01 DataFrame.
    @param tsa02_df - TSA02 DataFrame.
    @return Merged TSA data DataFrame.
    """
    if not event_info.tsa02_available:
        tsa01_df["Employee_ID"] = ""
        input_df = tsa01_df
    else:
        input_df = pd.merge(tsa01_df, tsa02_df, on="Confirmation_no", how="left",
                            validate="many_to_many")

    return input_df


def apply_fail_safe_conditions_charge_days(event_info, input_df):
    """
    Apply fail-safe conditions to calculate the charge days based on the departure and arrival
    dates in the input dataframe.
    @param event_info - Information about the event
    @param input_df - Input dataframe containing departure and arrival dates
    @return Updated input dataframe with the calculated charge days.
    """
    action = "apply_fail_safe_conditions_charge_days"
    input_df["Charge_Days"] = (input_df["Departure_Date"].apply(
        fail_safe_cls(dayfirst=True, errors='coerce').departure_date_validation) - input_df[
                                   "Arrival_Date"].apply(
        fail_safe_cls(dayfirst=True, errors='coerce').arrival_date_validation))

    # Use .apply() to extract the days from the timedelta object
    input_df["Charge_Days"] = input_df["Charge_Days"].apply(
        lambda x: x.days if pd.notnull(x) else None)

    input_df['Charge_Days'] = input_df['Charge_Days'].apply(fail_safe_cls().charge_days_validation)

    event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                 "Successfully applied fail-safe condition on Charge Days")
    return input_df


def apply_fail_safe_conditions_date_and_mapping(event_info, output_df):
    """
    Apply fail-safe conditions on date columns in the output dataframe and log the actions taken.
    @param event_info - Information about the event
    @param output_df - The output dataframe to apply fail-safe conditions to
    @return None
    """
    action = "apply_fail_safe_conditions_date_and_mapping"

    output_df['Daily_Date'] = output_df['Daily_Date'].apply(
        fail_safe_cls().daily_date_validation)
    event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                 "Successfully applied fail-safe condition on Daily Date")
    output_df['Arrival_Date'] = output_df['Arrival_Date'].apply(
        fail_safe_cls(dayfirst=True).arrival_date_validation)
    event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                 "Successfully applied fail-safe condition on Arrival Date")
    output_df['Departure_Date'] = output_df['Departure_Date'].apply(
        fail_safe_cls(dayfirst=True).departure_date_validation)
    event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                 "Successfully applied fail-safe condition on Departure Date")

    datetime_type = "datetime64[ns]"
    data_type_mapping = {'Confirmation_no': str, 'New_Room_Type': str, 'Original_Room_Type': str,
                         'Charge_Days': str, 'Room_No': str, 'Notes': str, 'Market_Segment': str,
                         'Product_Category': str, 'Product': str, 'Daily_Date': datetime_type,
                         'Arrival_Date': datetime_type, 'Departure_Date': datetime_type}

    output_df = output_df.astype(data_type_mapping, errors='ignore')

    date_cols = ['Departure_Date', 'Daily_Date', 'Arrival_Date']
    for each_col in date_cols:
        try:
            output_df[each_col] = output_df[each_col].dt.date
        except custom_exceptions as e:
            print(e)
            continue
    event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                 "Successfully applied fail-safe condition on Dates and Mapping")
    return output_df


def create_products_df(event_info):
    """Get the products for a given event info from the database and return them as a list of
    products in the form of dataframe"""
    action = "create_products_df"

    try:
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Creating product mapping for location code {str(event_info.location_code)}")

        product_mapping_df_opera_query = f"""
            SELECT DISTINCT lgp.name AS `Product_Name`, tpc.NAME AS `Product_Category`, 
                            lgp.productSKU as `Product_SKC`, lgp.productCode as `Product_Code`, 
                            Upper(tlp.locationID) as `Location_ID` 
            FROM tenant_product tp 
            JOIN tenant_product_category tpc ON tp.TENANT_PRODUCT_CATEGORY_ID = tpc.ID 
            JOIN location_group_product lgp ON lgp.TENANT_PRODUCT_ID = tp.id 
            JOIN location_group lg on lg.id=lgp.LOCATION_GROUP_ID 
            JOIN tenant_location_profile tlp on lg.tenant_location_id = tlp.id 
            JOIN tenant_location tl on lg.tenant_location_id = tl.id 
            where lgp.ACTIVE_STATUS = 0 and tl.ACTIVE_STATUS = 0 and
            Upper(tlp.locationID)='{event_info.location_code}' 
            AND tl.tenant_ID = {event_info.tenant_id} AND lgp.productCode is
            not null AND TRIM(lgp.productCode) != ''
        """

        result = ing_db_mysql.query(event_info, product_mapping_df_opera_query)
        if result:
            product_mapping_df = pd.DataFrame(list(result),
                                              columns=['Product_Name', 'Product_Category',
                                                       'Product_SKC',
                                                       'Product_Code', 'Location_ID'])

            product_mapping_df = product_mapping_df.fillna('').applymap(lambda x: str(x).strip())
            product_mapping_df['Product_Code'] = product_mapping_df['Product_Code'].str.split(',')
            product_mapping_df = product_mapping_df.explode('Product_Code').reset_index(drop=True)

            product_mapping_other_revenue_df = \
            product_mapping_df.query("Product_Category != 'Room Upsell'")[
                ['Product_Name', 'Product_Category', 'Product_Code']]
            return product_mapping_df, product_mapping_other_revenue_df
        else:
            raise LookupError(
                f"Product mapping information not available in master DB (MySQL) for location "
                f"code '{event_info.location_code}'")

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while creating product df for '{event_info.tsa01_file}' "
                           f"file for '{event_info.tenant_id}' tenant_id and '"
                           f"{event_info.location_code}' location.",
                           e)
        return None, None


def unrecognized_product_code(event_info, input_with_category_df):
    """
    Identify and handle unrecognized product codes in the input data.
    @param event_info - Information about the event
    @param input_with_category_df - Dataframe containing input data with categories
    @return Dataframe containing unrecognized product codes
    """
    action = "unrecognized_product_code"

    try:
        unrecognized_product_codes_df_query = "select i.Confirmation_no, i.Product_Code from " \
                                              "input_with_category_df i where i.Product_Category " \
                                              "is null"
        unrecognized_product_codes_df = sqldf(unrecognized_product_codes_df_query, locals())
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"input_with_category_df: {len(input_with_category_df)}")
        if not unrecognized_product_codes_df.empty:
            event_info.unrecognized_product_codes_list = \
                unrecognized_product_codes_df.values.tolist()

            event_info.app_log.warn(event_info.trace_id, event_info.span_id, action,
                         f"The report contained some transactions with PMS product codes that are "
                         f"not configured in the application."
                         "Those transactions will be marked as error within IN-Gauge."
                         "Please configure the corresponding products and fix the transactions "
                         "that are in error status."
                         f"Here is the list of [Confirmation no, PMS Product code] values for "
                         f"transactions which are in error status: "
                         f"{event_info.unrecognized_product_codes_list}")

        return unrecognized_product_codes_df
    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Unable to validate the values in the column. Here is the error "
                           f"{str(e)}",
                           e)


def create_room_upsell(event_info, input_with_category_df, product_mapping_df):
    """
        Creates room upsell based on the provided dataframes and event information.
    """
    action = "create_room_upsell"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        input_room_upsell_query = "SELECT * FROM input_with_category_df WHERE Trim(" \
                                  "Product_Category) in ('Room Upsell') " \
                                  "and (Arrival_Date = Departure_Date or TRIM(UPPER(resv_status))" \
                                  " not in ('CHECKED OUT', 'CHECK OUT'))"

        input_room_upsell_df = sqldf(input_room_upsell_query, locals())
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"input_with_category_df: {len(input_with_category_df)}")
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"product_mapping_df: {len(product_mapping_df)}")
        input_room_upsell_product_df_query = "SELECT i.*, m.Product_Name AS Product FROM " \
                                             "input_room_upsell_df " \
                                             "i LEFT JOIN product_mapping_df m ON i.Pkg_Code = " \
                                             "m.Product_Code and " \
                                             "i.New_Room_Type = m.Product_SKC "
        input_room_upsell_product_df = sqldf(input_room_upsell_product_df_query, locals())

        input_room_upsell_df_count = len(input_room_upsell_df)
        input_room_upsell_product_df_count = len(input_room_upsell_product_df)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Number of rows in the input dataframe for product category of Room Upsell "
                     f"is: {input_room_upsell_df_count}")

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Number of rows in the input dataframe for product category of Room Upsell "
                     f"after adding product is: {input_room_upsell_product_df_count}")

        if input_room_upsell_df_count != input_room_upsell_product_df_count:
            raise ValueError(
                'Failed: The number of rows in the input dataframe was changed after product was '
                'added for product category of Room Upsell.')

        try:
            unrecognized_new_room_types_df_query = "select i.Confirmation_no, i.New_Room_Type " \
                                                   "from input_room_upsell_product_df i where " \
                                                   "i.Product_Category is not null and i.Product " \
                                                   "is null"
            unrecognized_new_room_types_df = sqldf(unrecognized_new_room_types_df_query, locals())

            if not unrecognized_new_room_types_df.empty:
                event_info.unrecognized_new_room_types_list = \
                    unrecognized_new_room_types_df.values.tolist()
                event_info.app_log.warn(event_info.trace_id, event_info.span_id, action,
                             f"The report contained some transactions with product IDs (room "
                             f"types) that are not configured in the application."
                             "Those transactions will be marked as error within IN-Gauge."
                             "Please configure the corresponding product IDs (room types) and fix "
                             "the transactions that are in error status."
                             f"Here is a list of [Confirmation no,  Product ID (room type)] "
                             f"values for transactions which are in error status: "
                             f"{event_info.unrecognized_product_codes_list}")

        except custom_exceptions as e:
            log_and_send_email(event_info, action,
                               f"Failed: Unable to get a list of unrecognized product IDs (room "
                               f"types). Here is the "
                               f"error message: {str(e)}", e)

        return input_room_upsell_product_df

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while doing create room upsell for '{tenant_id}' tenant_id "
                           f"and '{location_code}' location.",
                           e)
        return None


def create_other_revenue(event_info, input_with_category_df, product_mapping_other_revenue_df):
    """
        Creates other revenue data based on the provided dataframes and event information.
    """
    action = "create_other_revenue"
    tenant_id = event_info.tenant_id
    location_code = event_info.location_code

    try:
        input_non_room_upsell_df_query = "SELECT * FROM input_with_category_df WHERE TRIM(" \
                                         "Product_Category)!='Room Upsell' or Product_Category is" \
                                         " null"
        input_non_room_upsell_df = sqldf(input_non_room_upsell_df_query, locals())
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"input_with_category_df: {len(input_with_category_df)}")
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"product_mapping_other_revenue_df: {len(product_mapping_other_revenue_df)}")

        input_non_room_upsell_product_all_df_query = "SELECT i.*,m.Product_Name AS Product FROM " \
                                                     "input_non_room_upsell_df i LEFT JOIN " \
                                                     "product_mapping_other_revenue_df m ON " \
                                                     "i.Pkg_Code = m.Product_Code "

        input_non_room_upsell_product_all_df = sqldf(input_non_room_upsell_product_all_df_query,
                                                     locals())

        input_non_room_upsell_df_count = len(input_non_room_upsell_df)
        input_non_room_upsell_product_all_df_count = len(input_non_room_upsell_product_all_df)

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Number of rows in the input dataframe for product category of Non Room "
                     f"Upsell is: {input_non_room_upsell_df_count}")

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Number of rows in the input dataframe for product category of Non Room "
                     f"Upsell after adding product is: "
                     f"{input_non_room_upsell_product_all_df_count}")

        if input_non_room_upsell_df_count != input_non_room_upsell_product_all_df_count:
            raise ValueError(
                'Failed: The number of rows in the input dataframe was changed after product was '
                'added for product category of Non Room Upsell')

        return input_non_room_upsell_product_all_df

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while doing create other revenue for '{tenant_id}' "
                           f"tenant_id and '{location_code}' location.",
                           e)
        return None


def remove_non_room_upsell_records(event_info, input_non_room_upsell_product_all_df):
    """
        Removes non-room upsell records from the provided DataFrame based on event information.
    """
    action = "remove_non_room_upsell_records"

    try:
        input_non_room_upsell_product_final_df_query = "SELECT * FROM " \
                                                       "input_non_room_upsell_product_all_df " \
                                                       "WHERE Daily_Date != Departure_Date or" \
                                                       " Trim(Product) = 'Late Check Out'"
        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"input_non_room_upsell_product_all_df"
                     f": {len(input_non_room_upsell_product_all_df)}")
        input_non_room_upsell_product_final_df = sqldf(input_non_room_upsell_product_final_df_query,
                                                       locals())

        event_info.app_log.info(event_info.trace_id, event_info.span_id, action,
                     f"Number of rows in the input dataframe for product category of Non Room "
                     f"Upsell after removing records on departure "
                     f"date: {len(input_non_room_upsell_product_final_df)}")
        return input_non_room_upsell_product_final_df

    except custom_exceptions as e:
        log_and_send_email(event_info, action,
                           f"Exception while doing remove non room upsell records for"
                           f" '{event_info.tenant_id}' tenant_id and '{event_info.location_code}'"
                           f" location.",
                           e)
        return None


def log_and_send_email(event_info, action, message, exception):
    """log the error message and send notification for the same"""
    record = event_info.app_log.error(event_info.trace_id, event_info.span_id, action, message, exception)
    SendEmailNotification(record).execute()
