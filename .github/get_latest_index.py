import os
import re
import requests
from google.cloud import bigquery

# Set up BigQuery client
project_id='idc-external-025'
client = bigquery.Client(project=project_id)

# Get current index version
file_path='IDCBrowser/Resources/csv_index.sql'
with open(file_path, 'r') as file:
    content = file.read()
current_index_version = re.search(r'idc_v(\d+)', content).group(1)
print('idc_version_in_index: '+current_index_version +'\n')

# Get latest IDC release version
view_id = "bigquery-public-data.idc_current.dicom_all_view"
view = client.get_table(view_id)
latest_idc_release_version= re.search(r'idc_v(\d+)', view.view_query).group(1)
print('latest_idc_release_version: '+latest_idc_release_version +'\n')

# Check if current index version is outdated
if current_index_version < latest_idc_release_version:
  # Update SQL query
  modified_sql_query = re.sub(r'idc_v(\d+)', 'idc_v'+latest_idc_release_version, content)
  print('modified_sql_query:\n'+modified_sql_query)
  
  # Overwrite the existing SQL file with the modified SQL query
  with open(file_path, 'w') as file:
    file.write(modified_sql_query)
  
  # Execute SQL query and save result as CSV
  df = client.query(modified_sql_query).to_dataframe()
  csv_file_name = 'csv_index_'+'idc_v'+latest_idc_release_version+'.csv'
  df.to_csv(csv_file_name, escapechar='\\')

  # Set up GitHub API request headers
  headers = {
    'Accept': 'application/vnd.github+json',
    'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
    'X-GitHub-Api-Version': '2022-11-28'
  }

  # Create a new release
  data = {
    'tag_name': 'v' + latest_idc_release_version,
    'target_commitish': 'main',
    'name': 'v' + latest_idc_release_version,
    'body': 'Found newer IDC release with version '+latest_idc_release_version+ '. So updating the index also from idc_v'+current_index_version+' to idc_v'+latest_idc_release_version,
    'draft': False,
    'prerelease': False,
    'generate_release_notes': False
  }
  response = requests.post('https://api.github.com/repos/vkt1414/SlicerIDCBrowser/releases', headers=headers, json=data)

  # Check if release was created successfully
  if response.status_code == 201:
    # Get upload URL for release assets
    upload_url = response.json()['upload_url']
    upload_url = upload_url[:upload_url.find('{')]
    upload_url += '?name=' + csv_file_name

    # Upload CSV file as release asset
    headers['Content-Type'] = 'application/octet-stream'
    with open(csv_file_name, 'rb') as data:
      response = requests.post(upload_url, headers=headers, data=data)

      # Check if asset was uploaded successfully
      if response.status_code != 201:
        print('Error uploading asset: ' + response.text)
  else:
    print('Error creating release: ' + response.text)

  # Update csv_index_path in IDCClient.py
  idcclient_path = 'IDCBrowser/IDCBrowserLib/IDCClient.py'
  with open(idcclient_path, 'r') as file:
    idcclient_content = file.read()
  new_csv_index_path = 'https://github.com/vkt1414/SlicerIDCBrowser/releases/download/v' + latest_idc_release_version + '/' + csv_file_name
  updated_idcclient_content = re.sub(r"https://github.com/vkt1414/SlicerIDCBrowser/releases/download/v\d+\.\d+\.\d+/index_v\d+\.csv", new_csv_index_path, idcclient_content)
  with open(idcclient_path, 'w') as file:
    file.write(updated_idcclient_content)
