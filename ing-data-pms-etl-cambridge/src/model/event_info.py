"""
Module for defining the EventInfo class, which holds various attributes related to event processing.
"""

import os
from EtlServices.fpg_app_log import FpgAppLog
from EtlServices.common_params import CommonEventInfo


class EventInfo(CommonEventInfo):
    """
    A class to represent event information with various attributes related to event processing.

    Attributes:
        trace_id (str): Trace ID for tracing the event.
        span_id (str): Span ID for tracing the event.
        tenant_id (int): ID of the tenant.
        tenant_location_id (int): ID of the tenant location.
        industry_id (int): ID of the industry.
        location_id (int): ID of the location.
        region_id (int): ID of the region.
        tsa01_file (str): TSA01 file related to the event.
        tsa02_file (str): TSA02 file related to the event.
        tsa03_file (str): TSA03 file related to the event.
        tsa04_file (str): TSA04 file related to the event.
        request_id (str): Request ID for the event.
        request_event (str): The event request.
        files_list (list): List of files related to the event.
        file_dict_list (list): List of file dictionaries.
        file_dict (dict): Dictionary of files.
        room_metric_df (DataFrame): DataFrame containing room metrics.
        no_upsell_dates_list (list): List of dates with no upsell.
        file_encoding (str): Encoding of the file.
        location_code (str): Code of the location.
        file_location_code (str): File location code.
        metric_date (str): Date of the metric.
        daily_date (str): Daily date.
        metric_type (str): Type of metric.
        app_env (str): Application environment.
        etl_type (str): Type of ETL.
        confirmation_no_list (list): List of confirmation numbers.
        input_file_extension (str): Extension of the input file.
        unrecognized_product_codes_list (list): List of unrecognized product codes.
        unrecognized_new_room_types_list (list): List of unrecognized new room types.
        output_metric (str): Output metric.
        output_file_name (str): Name of the output file.
        s3_target_dir (str): Target directory in S3.
        s3_output_bucket (str): Output bucket in S3.
        metric_file_dict (dict): Dictionary of metric files.
        import_id (int): Import ID.
        temp_file_path (str): Path to the temporary file.
        processed_id (int): Processed ID.
        utility_file_type (int): Type of utility file.
        product (str): Product name.
        product_category (str): Category of the product.
        api_url (str): URL of the API.
        tsa01_available (bool): Availability of TSA01 file.
        tsa02_available (bool): Availability of TSA02 file.
        tsa03_available (bool): Availability of TSA03 file.
        tsa04_available (bool): Availability of TSA04 file.
        drop_headers (bool): Whether to drop headers.
        raw_file_name (str): Name of the raw file.
        upload_s3_bucket_name (str): Name of the S3 bucket for upload.
        upload_file_object (object): File object to be uploaded.
    """

    room_metric_df = None
    no_upsell_dates_list = []
    file_encoding = None

    confirmation_no_list = None

    unrecognized_product_codes_list = []
    unrecognized_new_room_types_list = []

    s3_target_dir = os.environ["s3_target_dir"]
    s3_output_bucket = os.environ["s3_output_bucket"]
    product = "Complimentary"
    product_category = "Other Revenue"

    drop_headers = True
    app_log = FpgAppLog()
