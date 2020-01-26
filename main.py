# coding: utf-8

import twitter
import requests
import json
import sys
import time
import os
from dotenv import load_dotenv


def tweet_list_to_tuple(s):
    return (
        s.id,
        (
            list(
                map(
                    lambda m: m.media_url,
                    filter(lambda m: m.type == "photo", s.media),  # noqa: E501
                )
            )
            if s.media is not None
            else []
        ),
    )


def resresh_token_to_access_token():
    data = {
        "refresh_token": os.environ.get("REFRESH_TOKEN"),
        "client_id": os.environ.get("CLIENT_ID"),
        "client_secret": os.environ.get("CLIENT_SECRET"),
        "grant_type": "refresh_token",
    }
    response = requests.post(
        "https://www.googleapis.com/oauth2/v4/token", data=data
    )  # noqa: E501
    return json.loads(response.text)["access_token"]


def fetch_tweet(name):
    api = twitter.Api(
        consumer_key=os.environ.get("CONSUMER_KEY"),
        consumer_secret=os.environ.get("CONSUMER_SECRET"),
        access_token_key=os.environ.get("ACCESS_TOKEN_KEY"),
        access_token_secret=os.environ.get("ACCESS_TOKEN_SECRET"),
    )

    statuses = api.GetUserTimeline(screen_name=name)
    return dict(
        filter(lambda m: m[1], map(lambda m: tweet_list_to_tuple(m), statuses))
    )  # noqa: E501


def create_upload_header(access_token, key, i):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream",
        "X-Goog-Upload-File-Name": f"{key}_{i}",
        "X-Goog-Upload-Protocol": "raw",
    }


def upload_image(tweet, access_token):
    for key, value in tweet.items():
        for i, url in enumerate(value):
            for count in range(2):
                image_response = requests.get(url)
                image = image_response.content

                upload_response = requests.post(
                    "https://photoslibrary.googleapis.com/v1/uploads",
                    data=image,
                    headers=create_upload_header(access_token, key, i),
                )
                if int(upload_response.status_code) != 200:
                    print(f"upload is fail. image url is {url}")
                    time.sleep(3)
                    continue

                data_dict = {
                    "newMediaItems": [
                        {
                            "description": "item-description",
                            "simpleMediaItem": {
                                "uploadToken": upload_response.text
                            },  # noqa: E501
                        }
                    ]
                }
                create_response = requests.post(
                    "https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate",
                    data=json.dumps(data_dict),
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )
                if int(create_response.status_code) != 200:
                    print(f"create is fail. image url is {url}")
                    time.sleep(3)
                    continue
                else:
                    break
            else:
                sys.exit(1)


def execute():
    load_dotenv(verbose=True)

    access_token = resresh_token_to_access_token()

    for user in str(os.environ.get("USER_LIST")).split(","):
        print(f"{user} is start.")
        upload_image(fetch_tweet(user), access_token)
        print(f"{user} is end.")


execute()
