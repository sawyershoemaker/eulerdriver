# eulerdriver

A Python webdriver tool for submitting solutions to Project Euler problems. Uses Selenium with Brave browser to handle login, navigation, and answer submission.

## What it does

- Automatically logs into Project Euler
- Finds unsolved problems from your progress page
- Submits answers from a text file
- Handles rate limiting and captchas
- Tracks solved/failed problems

## Requisites
- Brave browser (created this on a laptop without edge/chrome sorry)
- python
- stuff from requirements.txt
- an answerlist, (i recommend lucky-bai's)

## How it works

we are using a two-part system:

- **EulerWebdriver**: browser automation, login, navigation, and answer submission
- **EulerSolver**: workflow, loads answers from file, and coordinates the solving process

>It will automatically download ChromeDriver and find your Brave browser installation. The solver reads answers from a text file and submits them one by one, tracking which problems are already solved to avoid duplicates.
