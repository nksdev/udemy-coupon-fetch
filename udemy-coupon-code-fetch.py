import os
import threading
import requests
from flask import Flask, request, render_template_string, redirect, url_for, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import random
import time
from queue import Queue
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor
from fake_useragent import UserAgent
import cloudscraper

# Auto-install missing dependencies
def install_missing_packages():
    required_packages = ['flask', 'requests', 'beautifulsoup4', 'fake_useragent', 'cloudscraper']
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing missing package: {package}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_missing_packages()

app = Flask(__name__)
visited_links = set()
coupon_links = []
ua = UserAgent()
scraper = cloudscraper.create_scraper()

scanning = False
progress = 0
queue = Queue()
session = requests.Session()
stop_signal = threading.Event()

# Function to fetch coupon links
def fetch_coupon_links(url):
    global scanning, progress
    try:
        if url in visited_links or not scanning or stop_signal.is_set():
            return
        print(f"Checking URL: {url}")
        visited_links.add(url)
        headers = {'User-Agent': ua.random}
        response = scraper.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True)]
        new_coupons = [link for link in links if '?couponCode=' in link]
        coupon_links.extend(new_coupons)
        queue.put(f"Found {len(new_coupons)} coupon links at {url}")
        progress += 1
        time.sleep(random.uniform(1, 5))  # Random delay to mimic human behavior
        sub_links = [link for link in links if link not in visited_links and urlparse(link).netloc == urlparse(url).netloc]
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(fetch_coupon_links, sub_links)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")

@app.route('/', methods=['GET', 'POST'])
def index():
    html_template = """
  <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coupon Link Finder</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
        /* Optional: custom styles can be added here */
    </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen">
    <div class="container mx-auto p-6 bg-white rounded-lg shadow-lg">
        <h2 class="text-2xl font-bold text-center text-gray-700 mb-6">Enter Website URLs</h2>
        <form method="POST" class="mb-4">
            <input type="text" name="websites" placeholder="Enter URLs, comma-separated" required class="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
            <button type="submit" name="action" value="start" class="mt-4 w-full p-3 bg-blue-600 text-white font-semibold rounded-md hover:bg-blue-500 transition duration-200">Start Scan</button>
        </form>
        <a href="/stop">
            <button class="w-full p-3 bg-red-600 text-white font-semibold rounded-md hover:bg-red-500 transition duration-200">Stop Scan</button>
        </a>
        <h3 class="mt-6 text-xl text-green-600" id="progress">Progress: {{ progress }}</h3>
        <div class="results mt-4">
            <h3 class="text-lg font-semibold text-gray-700">Coupon Links Found:</h3>
            <ul class="list-disc list-inside">
                {% for link in coupon_links %}
                <li class="mt-2">
                    <a href="{{ link }}" target="_blank" class="text-blue-600 hover:underline">{{ link }}</a>
                </li>
                {% endfor %}
            </ul>
        </div>
    </div>
</body>
</html>
    """
    if request.method == 'POST':
        websites = request.form['websites'].split(',')
        num_threads = 5
        thread = threading.Thread(target=scan_websites, args=(websites, num_threads))
        thread.start()
        return redirect(url_for('index'))
    return render_template_string(html_template, scanning=scanning, progress=progress, coupon_links=coupon_links)

@app.route('/stop')
def stop():
    global scanning
    stop_signal.set()
    scanning = False
    return redirect(url_for('index'))

@app.route('/progress')
def get_progress():
    return jsonify({'progress': progress, 'logs': list(queue.queue)})

# Function to scan websites
def scan_websites(websites, num_threads):
    global scanning, progress
    scanning = True
    progress = 0
    stop_signal.clear()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        executor.map(fetch_coupon_links, websites)
    scanning = False

if __name__ == '__main__':
    app.run(debug=True)
