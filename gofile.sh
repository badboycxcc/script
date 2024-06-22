#!/bin/bash

function get_best_eu_server() {
  eu_servers=$(curl -s -X GET 'https://api.gofile.io/servers' | jq -r '.data.servers[0].name')
  best_server=$(echo "$eu_servers" | head -n1) 
  echo "$best_server"
}

while getopts ":f:d:" opt; do
  case ${opt} in
    f )
      FILE_TO_UPLOAD=$OPTARG
      ;;
    d )
      DIR_TO_UPLOAD=$OPTARG
      ;;
    \ )
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
    : ) 
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done


function upload_file() {

  echo "Uploading $FILE_TO_UPLOAD..."
  server=$(get_best_eu_server)

  if [[ -z "$server" ]]; then
    echo "Error: Failed to get a valid server."
    exit 1
  fi

  # echo "Server Selected: $server"

  upload_response=$(curl -s -X POST "https://$server.gofile.io/contents/uploadfile" \
                    -F "file=@$FILE_TO_UPLOAD")
  if [[ $upload_response =~ "status\":\"ok" ]]; then
    download_page=$(echo $upload_response | jq -r '.data.downloadPage')
    echo "Upload successful. Download Page: $download_page"
  else
    echo "Upload failed. Unexpected response format."
  fi

  timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  if [[ -n "$download_page" ]]; then
    echo "$timestamp - Upload successful: $download_page ($file)" >> upload.log
  else
    echo "$timestamp - Upload failed. Response: $upload_response ($file)" >> upload.log
  fi
}

upload_file