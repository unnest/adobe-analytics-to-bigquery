import json
import requests
import time as tt
import pandas as pd
from datetime import datetime, date, timedelta
from dateutil import parser
from google.cloud import bigquery
from google.cloud import secretmanager
from google import auth


_, project_id = auth.default()
secret_manager_client = secretmanager.SecretManagerServiceClient()

tok = secret_manager_client.access_secret_version(
    request={"name": f"projects/{project_id}/secrets/tok/versions/latest"}
).payload.data.decode()

url = secret_manager_client.access_secret_version(
    request={"name": f"projects/{project_id}/secrets/url/versions/latest"}
).payload.data.decode()


headers = {"Content-Type": "application/json"}


def extract(input_date):
    params = (
        ("token_auth", TOK),
        ("apiAction", "getCustomReport"),
        ("language", "en"),
        ("apiModule", "CustomReports"),
        ("date", input_date),
        ("idCustomReport", 6),  # ID du rapport personnalisé dans matomo
        ("filter_limit", -1),
        ("format", "JSON"),
    )
    # 'https://onduline.matomo.cloud/?module=API&method=API.getProcessedReport&idSite=1&period=day&flat=1'
    r = requests.get(url, params=params, headers=headers, verify=False)
    # Remplacer MONSITE par celui dans votre URL matomo
    j = json.loads(r.text)
    return j


def execute_bq_job(df):
    print("start_bq")
    cl = bigquery.Client()
    # Ajuster noms ici
    PROJECT_ID = "Onduline"
    DATASET_ID = "test"
    table_name = "test2"

    try:
        dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
        dataset.location = "EU"
        dataset = cl.create_dataset(dataset)  # API request
    except:
        print("dataset not created")
    dataset = cl.dataset(DATASET_ID)
    job_config = bigquery.LoadJobConfig()
    job_config.autodetect = True
    job_config.write_disposition = "WRITE_APPEND"
    job_config.create_disposition = "CREATE_IF_NEEDED"

    load_job = cl.load_table_from_dataframe(
        df, dataset.table(table_name), job_config=job_config
    )  # API request
    print("Starting job {}".format(load_job.job_id))

    load_job.result()  # Waits for table load to complete.
    print("Job finished.")


def clean_columns(df):
    df.columns = df.columns.str.replace(r"(", "")
    df.columns = df.columns.str.replace(r")", "")
    df.columns = df.columns.str.replace(r"[", "")
    df.columns = df.columns.str.replace(r"]", "")
    return df.columns.str.replace(" ", "_")


def cloud_handler(request):
    # Par défaut si aucun paramètre de date n'est renseigné la fonction tournera sur la donnée de la veille
    """
    :param request:
    :return: success/error message
    """
    request_json = request.get_json(silent=True)
    request_args = request.args
    default_date = datetime.now() - timedelta(days=1)

    if request_json and "start_date" in request_json:
        start_date = request_json["start_date"]
    elif request_args and "start_date" in request_args:
        start_date = request_args["start_date"]
    else:
        start_date = default_date.strftime("%Y-%m-%d")

    if request_json and "end_date" in request_json:
        end_date = request_json["end_date"]
    elif request_args and "end_date" in request_args:
        end_date = request_args["end_date"]
    else:
        end_date = default_date.strftime("%Y-%m-%d")

    # command: zip -r cloud_function.zip applibs/bigquery_util.py applibs/google_cred.json main.py requirements.txt
    try:
        print(f"Start processing at: {datetime.now().isoformat()}")

        input_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        delta = timedelta(days=1)
        print("end_date : ", end_date)
        while input_date <= end_date:
            print("input_date : ", input_date)
            # Extract data
            request_data = extract(input_date)
            data = request_data["reportData"]
            df = pd.DataFrame(data=data)
            # print(data)
            date = parser.parse(request_data["prettyDate"]).strftime("%Y-%m-%d")
            json_data = []
            processed_datetime = str(datetime.now())
            input_date += delta
            # store data

            df.columns = clean_columns(df)
            df["_processed_datetime"] = processed_datetime
            execute_bq_job(df)
            print(f"End processing at: {datetime.now().isoformat()}")

            if res != "success":
                print("error: " + res)
                return {"message": res}, 400

        return {"message": "Data saved successfully."}, 200

    except Exception as error_info:
        print(error_info)
        return {"message": error_info}, 400
