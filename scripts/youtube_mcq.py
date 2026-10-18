
import json
import os
import urllib.request
import urllib.error
import base64

from youtube_transcript_api import YouTubeTranscriptApi

CHANNEL_ID = "UCkk7LhDu39GiacOLVRb2xSA"
GEMINI_MODEL = "gemini-2.5-flash"


def get_latest_video():
    url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={CHANNEL_ID}"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.read())

    ns = {"yt": "http://www.youtube.com/xml/schemas/2015"}
    entry = root.find("{http://www.w3.org/2005/Atom}entry")
    if entry is None:
        return None

    return {
        "video_id": entry.findtext("yt:videoId", namespaces=ns),
        "title": entry.findtext(
            "{http://www.w3.org/2005/Atom}title"
        ),
    }


def get_transcript(video_id):
    transcript = YouTubeTranscriptApi().fetch(
        video_id, languages=["bn", "en", "hi"]
    )
    text = " ".join(item.text for item in transcript)
    if len(text) < 100:
        raise RuntimeError("ট্রান্সক্রিপ্ট যথেষ্ট দীর্ঘ নয়")
    return text[:30000]


def generate_questions(title, transcript):
    api_key = os.environ["GEMINI_API_KEY"]
    prompt = f"""
তুমি বাংলাদেশের BCS পরীক্ষার প্রশ্নপ্রণেতা।
ভিডিওর শিরোনাম: {title}
ভিডিওর ট্রান্সক্রিপ্ট:
{transcript}

শুধু বৈধ JSON দাও। মোট ৫০টি মানসম্মত বাংলা MCQ তৈরি করো।
তথ্য ট্রান্সক্রিপ্টের সঙ্গে সামঞ্জস্যপূর্ণ রাখো।
প্রতিটি প্রশ্নে চারটি অপশন ও একটি সঠিক উত্তর থাকবে।
JSON-এর গঠন:
{{
  "questions": [
    {{
      "bn": "বাংলা প্রশ্ন",
      "en": "English translation of question",
      "o": [
        ["বাংলা অপশন ১", "Option 1"],
        ["বাংলা অপশন ২", "Option 2"],
        ["বাংলা অপশন ৩", "Option 3"],
        ["বাংলা অপশন ৪", "Option 4"]
      ],
      "a": 0,
      "eb": "বাংলায় সংক্ষিপ্ত ব্যাখ্যা",
      "ee": "Short explanation in English"
    }}
  ]
}}
a হলো সঠিক অপশনের index: 0, 1, 2 অথবা 3।
ঠিক ৫০টি প্রশ্ন দাও। JSON-এর বাইরে কোনো লেখা দেবে না।
"""
    payload = json.dumps({
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3
        }
    }).encode()

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent"
    )
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read())

    text = result["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(text)
    questions = data.get("questions", [])

    if len(questions) != 50:
        raise RuntimeError(
            f"৫০টি প্রশ্ন তৈরি হয়নি; পাওয়া গেছে {len(questions)}টি"
        )

    for q in questions:
        if not all(k in q for k in ("bn", "en", "o", "a", "eb", "ee")):
            raise RuntimeError("প্রশ্নের JSON কাঠামো সঠিক নয়")
        if len(q["o"]) != 4 or q["a"] not in range(4):
            raise RuntimeError("অপশন বা সঠিক উত্তর সঠিক নয়")

    return questions


def publish_questions(video, questions):
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    path = "questions.json"
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "JobSphere-Prep-Automation"
    }

    request = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            existing = json.loads(response.read())
        sha = existing["sha"]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            sha = None
        else:
            raise

    output = {
        "video_id": video["video_id"],
        "video_title": video["title"],
        "video_url": (
            "https://www.youtube.com/watch?v=" + video["video_id"]
        ),
        "questions": questions
    }

    content = base64.b64encode(
        json.dumps(output, ensure_ascii=False, indent=2).encode()
    ).decode()

    body = {
        "message": "Automatically generate MCQs from latest YouTube video",
        "content": content,
        "branch": "main"
    }
    if sha:
        body["sha"] = sha

    request = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode(),
        headers={**headers, "Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        print("প্রশ্ন প্রকাশ হয়েছে:", response.status)


def main():
    video = get_latest_video()
    if not video:
        print("কোনো ভিডিও পাওয়া যায়নি")
        return

    print("সর্বশেষ ভিডিও:", video["title"])
    transcript = get_transcript(video["video_id"])
    questions = generate_questions(video["title"], transcript)
    publish_questions(video, questions)


if __name__ == "__main__":
    main()
