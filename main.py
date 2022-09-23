from dataclasses import dataclass

import pyppeteer
import asyncio
from moviepy.editor import *
from pyppeteer.browser import Browser
from pyppeteer.element_handle import ElementHandle
from pyppeteer.page import Page
from mutagen.mp3 import MP3
from PIL import Image
from pathvalidate import sanitize_filename
import pyttsx3
import soundfile as sf
engine = pyttsx3.init()


@dataclass
class RedditPost:
    title: str
    points: str
    link: str

    def has_enough_points(self):
        return "k" in self.points

    def __str__(self):
        return f"{self.title} | {self.points} | {self.link}"

    @staticmethod
    async def from_element(page: Page, element: ElementHandle):
        title_element = await element.J("div.y8HYJ-y_lTUHkQIc1mdCq._2INHSNB8V5eaWp4P0rY_mE > a > div > h3")
        if title_element is None:
            return None
        try:
            title = await page.evaluate("(element) => element.textContent", title_element)
        except TypeError:
            return None
        link_element = await element.J("div.y8HYJ-y_lTUHkQIc1mdCq._2INHSNB8V5eaWp4P0rY_mE > a")
        link = await page.evaluate("(element) => element.href", link_element)

        points_element = await element.J("div._1rZYMD_4xY3gRcSS3p8ODO")
        points = await page.evaluate("(element) => element.innerHTML", points_element)

        return RedditPost(title, points, link)

subreddit = "AskReddit"

async def remove_unwanted(posts: list[ElementHandle]) -> list[ElementHandle]:
    for post in posts:
        pot_ad = await post.J("span._2oEYZXchPfHwcf9mTMGMg8.V0WjfoF5BV7_qbExmbmeR")
        if pot_ad is not None:
            posts.remove(post)
            continue
        pot_ad = await post.J("#t3_whw8qz")
        if pot_ad is None:
            posts.remove(post)
            continue
    return posts


async def main():
    global subreddit
    if not os.path.exists('completed.txt'):
        open('completed.txt', 'w').close()
    subreddit = input("Subreddit: ")
    print("Launching browser...")
    browser = await pyppeteer.launch(headless=False)
    await start(browser)

    await asyncio.sleep(1000)
    await browser.close()

@dataclass
class TTSHelper:
    readouts: list[str]
    images: list[str]
    audio: list[str]
    def __init__(self):
        self.readouts = []
        self.images = []
        self.audio = []

def make_clip_from_index(index: int, tts: TTSHelper) -> ImageClip:
    audio = AudioFileClip(tts.audio[index])
    im = Image.open(tts.images[index])
    width, height = im.size
    ratio = width / height
    n_width = 900
    n_height = 900 * ratio
    image: ImageClip = ImageClip(tts.images[index], duration=(sf.SoundFile(tts.audio[index]).frames / sf.SoundFile(tts.audio[index]).samplerate) + 0.3).\
        set_audio(audio). \
        resize(n_width / width, n_height / height). \
        set_position(('center', 'center'))
    return image

import re
def make_video_from_tts(tts: TTSHelper):
    index = 0
    clips = []
    for clip in range(len(tts.images)):
        clips.append(make_clip_from_index(index, tts))
        index += 1
    video = concatenate_videoclips(clips)
    video.set_position(('center', 'center'))

    background: VideoFileClip = (VideoFileClip("background.mp4"))
    if background.duration + 10 > video.duration:
        back_start = int(random.randint(5, int(background.duration) - int(video.duration) - 5))
        print("back start: " + str(back_start))
        background = background.subclip(back_start, back_start + video.duration)
    else:
        background = background.subclip(5, video.duration + 5)
    final = CompositeVideoClip([background.crop(x1=1920/2 - 607.5/2, y1=0, x2=1920/2 + 607.5/2, y2=1080).resize(1.8).set_position(('center', 'center')),\
                                video.set_position(('center', 'center'))])
    print("Starting render...")
    final.write_videofile(sanitize_filename(tts.readouts[0]) + ".avi", fps=60,codec='libx264')
    f = open("completed.txt", 'a')
    f.write(sanitize_filename(tts.readouts[0]))
    f.close()
    for file in tts.images:
        os.remove(file)
    for file in tts.audio:
        os.remove(file)
import _thread as thread
async def generate_video_from_post(post: RedditPost, browser: Browser):
    global engine
    key = x = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(4))
    page = await browser.newPage()
    await page.goto(post.link)
    await page.waitForSelector("div._1oQyIsiPHYt6nx7VOmd1sz")
    head = await page.J("div._1oQyIsiPHYt6nx7VOmd1sz")
    title = await page.evaluate("(element) => element.textContent", await page.J("div.y8HYJ-y_lTUHkQIc1mdCq._2INHSNB8V5eaWp4P0rY_mE > div > h1"))
    print(f"Selected post: {title}")
    await page.setViewport({'width': 1920, 'height': 1080, 'deviceScaleFactor': 4})
    await head.screenshot(path=key + "head.png")
    tts: TTSHelper = TTSHelper()
    tts.readouts.append(title)
    tts.images.append(key + "head.png")
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)
    engine.save_to_file(title, key + f"head.wav")
    engine.runAndWait()
    sf.SoundFile(key + f"head.wav").frames
    # gtts = gTTS(title, slow=False, lang='en', tld='com.au')
    # gtts.save(key + f"head.mp3")
    tts.audio.append(key + f"head.wav")
    await asyncio.sleep(2)
    comments = await page.JJ("div._1z5rdmX8TDr6mqwNv7A70U")
    comments = comments[:4]
    index = 0
    for comment in comments:
        if await comment.J("div.RichTextJSON-root") is None:
            continue
        inner_html: str = await page.evaluate("(element) => element.innerHTML", await comment.J("div.RichTextJSON-root"))
        inner_html = inner_html.replace("\"", "\\\"")
        inner_html = inner_html.replace("M\\\">", "M\\\"><span>")
        inner_html = inner_html.replace("</p>", "</span></p>")
        connectives = ['.', ',', '!', '?', '-']
        for c in connectives:
            inner_html = inner_html.replace(f"{c}", f"{c}</span><span>")


        print(inner_html)
        await page.evaluate(f"(element) => element.innerHTML = \"{inner_html}\"", await comment.J("div.RichTextJSON-root"))
        texts = await comment.JJ("div > p > span")
        internal_index = 0
        for paragraph in texts:
            await page.evaluate("(element) => element.style.visibility='hidden'", paragraph)
        for paragraph in texts:
            await page.evaluate("(element) => element.style.visibility='visible'", paragraph)

            await comment.screenshot(path=key + f"comment_{index}_{internal_index}.png")
            text = await page.evaluate("(element) => element.textContent", paragraph)
            if len(text) == 0 or text in connectives:
                continue

            print(f"  Found comment: {text}")
            tts.readouts.append(text)
            tts.images.append(key + f"comment_{index}_{internal_index}.png")
            voices = engine.getProperty('voices')
            engine.setProperty('voice', voices[0].id)
            engine.save_to_file(text, key + f"audio_{index}_{internal_index}.wav")
            engine.runAndWait()
            tts.audio.append(key + f"audio_{index}_{internal_index}.wav")
            internal_index += 1
        index += 1
    print(f"Generated files for: {title}")
    # thread.start_new_thread(make_video_from_tts, (tts,))
    make_video_from_tts(tts)


import random, string
async def start(browser):
    formatted_posts = await get_posts(browser)

    formatted_posts = [p for p in formatted_posts if p.has_enough_points()]
    if len(formatted_posts) == 0:
        return


    count = 0
    for post in formatted_posts:
        if count == 4:
            break
        f = open('completed.txt', 'r')
        if sanitize_filename(post.title) in f.read() or os.path.exists(sanitize_filename(post.title) + ".avi"):
            print(f"Skipping duplicate: {post.title}")
            f.close()
            continue
        f.close()
        print(f"Making video for post: {post.title}")
        count += 1
        await generate_video_from_post(post, browser)
    print("Done")


async def get_posts(browser):
    page, posts = await get_posts_raw(browser)
    print(f"Number of posts found on r/{subreddit}: {str(len(posts))}")
    formatted_posts = []
    for post in posts:
        formatted_posts.append(await RedditPost.from_element(page, post))
    return formatted_posts


async def get_posts_raw(browser):
    page = await browser.newPage()
    print("Waiting for Reddit to load...")
    await page.goto("https://reddit.com/r/" + subreddit + "/top/?t=week")
    await page.waitForSelector("div.rpBJOHq2PR60pnwJlUyP0 > div")
    posts = await page.JJ("div.rpBJOHq2PR60pnwJlUyP0 > div")
    posts = await remove_unwanted(posts)
    return page, posts


asyncio.get_event_loop().run_until_complete(main())

