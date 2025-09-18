# eulerdriver
A Python webdriver tool for submitting solutions to Project Euler problems. Uses Selenium with Brave browser to handle login, navigation, and answer submission.

## what it does

- Automatically logs into Project Euler
- Finds unsolved problems from your progress page
- Submits answers from a text file
- Handles rate limiting and captchas (with automated OpenAI solving)
- Tracks solved/failed problems

## what do we need
- brave browser (created this on a laptop without edge/chrome sorry)
- python
- stuff from requirements.txt
- an answerlist, (i recommend lucky-bai's)
- openai api key
---
>eulerdriver will automatically download ChromeDriver and find your Brave browser installation. The solver reads answers from a text file and submits them one by one, tracking which problems are already solved to avoid duplicates.
---

## captchas!

i do not have the time to train an OCR on Euler's simplistic captchas so im offloading the work to `gpt5-mini` since it's the cheapest model i can find that consistently beats these captchas

---
here's a high level overview of how it currently works:
1. captcha is detected
2. captcha is screenshotted and downloaded
3. captcha is sent to model with a small text prompt
4. model returns solution
5. we delete image (gotta save those 4 mb)
6. we type solution
---
> please ensure your api key is in .env and is not shared with anyone else!