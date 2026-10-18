
import json
import os
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCkk7LhDu39GiacOLVRb2xSA"


def get_latest_video():
    url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={CHANNEL_ID}"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    namespace = {"yt": "http://www.youtube.com/xml/schemas/2015"}

    entry = root.find("{http://www.w3.org/2005/Atom}entry")

    if entry is None:
        return None

    video_id = entry.findtext("yt:videoId", namespaces=namespace)
    title = entry.findtext(
        "{http://www.w3.org/2005/Atom}title"
    )

    return {
        "video_id": video_id,
        "title": title
    }


if __name__ == "__main__":
    video = get_latest_video()

    if video:
        print(json.dumps(video, ensure_ascii=False, indent=2))
    else:
        print("No videos found.")
