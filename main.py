# coding: utf-8

import twitter
import requests
import json
import sys
import time
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials

# global variables
db = None
access_token = None


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


def fetch_tweet(name, since_id):
    api = twitter.Api(
        consumer_key=os.environ.get("CONSUMER_KEY"),
        consumer_secret=os.environ.get("CONSUMER_SECRET"),
        access_token_key=os.environ.get("ACCESS_TOKEN_KEY"),
        access_token_secret=os.environ.get("ACCESS_TOKEN_SECRET"),
        tweet_mode="extended",
    )

    statuses = api.GetUserTimeline(screen_name=name, since_id=since_id)
    return dict(
        filter(lambda m: m[1], map(lambda m: tweet_list_to_tuple(m), statuses))
    )  # noqa: E501


def generate_upload_header(key, i):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream",
        "X-Goog-Upload-File-Name": f"{key}_{i}",
        "X-Goog-Upload-Protocol": "raw",
    }


def generate_create_header():
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def upload_image(tweet):
    for key, value in tweet.items():
        for i, url in enumerate(value):
            for count in range(2):
                image_response = requests.get(url)
                image = image_response.content

                upload_response = requests.post(
                    "https://photoslibrary.googleapis.com/v1/uploads",
                    data=image,
                    headers=generate_upload_header(key, i),
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
                    headers=generate_create_header(),
                )
                if int(create_response.status_code) != 200:
                    print(f"create is fail. image url is {url}")
                    time.sleep(3)
                    continue
                else:
                    break
            else:
                sys.exit(1)


def init_application():
    load_dotenv(verbose=True)

    global db
    global access_token

    cred = credentials.Certificate(json.loads(os.environ.get("FIREBASE_KEY")))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    access_token = resresh_token_to_access_token()


def tasogare_image(event, context):
    init_application()

    firebase_collection = db.collection(os.environ.get("FIREBASE_COLLECTION_NAME"))
    docs = firebase_collection.get()
    for doc in docs:
        document_data = doc.to_dict()
        screen_name = document_data["screen_name"]
        print(f"{screen_name} is start.")
        tweet = fetch_tweet(screen_name, document_data["since_id"])
        if tweet:
            upload_image(tweet)
            firebase_collection.document(f"{doc.id}").set(
                {"screen_name": screen_name, "since_id": max(map(lambda m: m, tweet))}
            )
        print(f"{screen_name} is end.")
