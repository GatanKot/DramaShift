from datetime import datetime

import requests
import time
import math
import re
from scipy.stats import beta

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By


## TODO: I am counting child nodes for reply count, but we should find all children of these nodes and use THAT as
## count, but direct children matter more. Algo.

## TODO improve controversy / engagement (drama) algo
## TODO: just grab post info don't do it multiple times. Monitor times which were pulled and store.
## TODO: This finds just controversial posts, but delusions themselves are drama-worthy, which are unanimous, and controversy may be in comments of big threads
## i.e. a thread of 10k comments likely has subthread more dramatic than niche post elsewhere

## TODO Add unscored delete comparison unscored.arete.network/c/{community}/p/uuidofpost


def get_slugified_url(url, driver_path=r'C:\Program Files\WebDriver_proj\msedgedriver.exe'):
    # Set up Edge options
    options = Options()
    options.add_argument('--headless')  # Run in headless mode (optional)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # Initialize the Edge driver
    service = Service(driver_path)
    driver = webdriver.Edge(service=service, options=options)

    # Open the page
    driver.get(url)

    try:
        # Search for the first link that matches the specific pattern
        # Adjust the selector for a link with href in the format /c/{community}/p/{uuid}/{slug}/c
        link_element = driver.find_element(By.XPATH,
                                           "//a[contains(@href, '/c/') and contains(@href, '/p/') and contains(@href, '/c')]")

        # Extract the href attribute
        href = link_element.get_attribute('href')
        return href  # Return the link
    except Exception as e:
        print(f"Error: {e}")
        return None  # Return None if no link is found

    finally:
        # Close the driver
        driver.quit()


def get_posts(from_id=None, sort='new', community=None, rate_limit_s=1):
    url = "https://scored.co/api/v2/post/" + sort + "v2.json"
    params = {
        'community': community,
        'from': from_id if from_id else '',
    }
    response = requests.get(url, params=params)
    time.sleep(rate_limit_s)  # 600 / 10 minutes, or 1 / second
    return response.json() if response.status_code == 200 else None


def fetch_posts_in_timeframe(hour_end=25, hour_start=1, community="consumeproduct", relative_to_time=0):
    """
    get all posts from community that fall within time frame
    [current time - hour_start hours, current time - hour_end hours]

    :param relative_to_time: time in ms since last epoch that hour end and hour start are relative to
    :param hour_end: posts before hour_end hours before current_time will be ignored
    :param hour_start: posts after hour_start hours before current_time will be ignored
    :param community: name of scored.co/c/{community} e.g. consumeproduct, thedonald
    :return: list of post dicts
    """
    if not relative_to_time:
        relative_to_time = int(time.time() * 1000)  # current time

    all_posts = []
    from_id = None
    next_copy = -1
    post_hour_prev = 0
    while True:
        data = get_posts(from_id, community=community, sort='new')
        if not data['has_more_entries']:  # if has_more_entries is false the data we got is bad, we can pull from a different index
            next_copy -= 1
            print(f"No more entries: {data}\nTrying {next_copy}")  # gather page of posts from new starting at last
            from_id = all_posts[next_copy]['uuid']
            print(f"Couldn't fetch from {community} past {post_hour_prev}")
            print(f"New uuid: {from_id}")
            return all_posts   # above  doesn't fix the issue
        else:
            next_copy = -1

        if data and 'posts' in data:
            posts = data['posts']
            if len(all_posts):
                posts = posts[1:]  # remove duplicate entry (we fetch from last uuid inclusive)
            for post in posts:
                # Get post creation date (milliseconds)
                post_time = int(post['created'])
                new_hour_prev = ((relative_to_time - post_time) / (60 * 60 * 1000))
                print(new_hour_prev)
                if new_hour_prev < post_hour_prev:
                    print(f"Error with fetch occurred. Last time {post_hour_prev}, current {new_hour_prev}\n"
                          f"Community: {community}\nFrom id: {from_id}"
                          f"Posts: {all_posts}")
                    return all_posts
                post_hour_prev = new_hour_prev
                # If the post is outside the time frame, stop fetching
                if post_hour_prev > hour_end:
                    return all_posts
                # Add post if within the time frame
                if post_hour_prev >= hour_start:
                    #  post["slug"] = slugify(post["title"])
                    post["salted_link"] = f"https://scored.co/c/{community}/p/{post['uuid']}/c"
                    post["link"] = ""
                    all_posts.append(post)

            # Get the ID of the last post to use for the next request
            if posts:
                from_id = posts[next_copy]['uuid']
            else:
                break  # No more posts
        else:
            break  # No data or error

    return all_posts


def calculate_drama_score(up, down, comm):
    """
    Calculates the drama of a post using only up, down votes and comments. Time not controlled.
    Think of it as: up / down ratio estimates sentiment, sentiment_factor peaks at half 'agree' half 'disagree'
    Max comment engagement can only reach the limit of sentiment_factor. Piecewise function means you have diminishing
    returns after ~50 comments peaking at ~3000. Unit tests have examples but e.g.
    + 1  / - 1,  0 comments     = + 1000/ - 0, 3000 comments            = + 0 / - 100, 0 comments   ()      0.0
    + 50 / - 50, 28             = + 920 / - 80, 3000                    = + 0 / - 100, 47           (*)     0.2
    + 50 / - 50, 58             = + 880 / - 120, 3000                   = + 0 / - 100, 114          (**)    0.4
    + 50 / - 50, 97             = + 680 / - 320, 3000                   = + 0 / - 100, 3000         (***)   0.6
    + 500 / - 500, 170          = + 720 / - 280, 3000                   = + 180 / - 820, 3000       (****)  0.8
    + 500 / - 500, 3000         = + 500 / - 500, 3000                   = + 500 / - 500, 3000       (*****) 1.0
    todo high comment counts at intermediate controversiality are underweighted,
    :param up
    :param down
    :param comm
    :return: value between 0 and 1 higher is more dramatic
    """
    total_votes = up + down
    if total_votes == 0:
        return 0  # maybe a few comments but unlikely to have drama
    ratio = up / (up + down)

    #  piecewise from desmos

    if ratio <= 0.5:  # high negative sentiment is more dramatic
        if ratio < 0.1825:
            sentiment_factor = min(1, 0.6 + 6 * (ratio ** 2))
        else:
            sentiment_factor = min(1, 1 - 1.985 * ((ratio - 0.5) ** 2))
    else:
        if ratio > 0.884:
            sentiment_factor = min(1, 6 * ((ratio - 1) ** 2))
        else:
            sentiment_factor = min(1, 1 - 4.058 * ((ratio - 0.5) ** 2))
    if comm < 28:
        engagement_factor = (comm ** 3) / 100000
    elif comm < 58:
        engagement_factor = 0.2 + (comm - 27.144) / 150
    elif comm < 97:
        engagement_factor = 0.4 + ((comm - 57.144) ** 0.875) / 125
    elif comm < 170:
        engagement_factor = 0.6 + ((comm - 96.739) ** 0.75) / 125
    else:
        engagement_factor = 0.8 + ((comm - 169.83) ** 0.4) / 125  # exceeds 1 at 3296
    drama_score = sentiment_factor * engagement_factor
    return drama_score


def calculate_post_drama_score(post):
    return calculate_drama_score(post['score_up'], post['score_down'], post['comments'])


def sort_posts_by_drama(posts):
    """

    :param posts:
    :return: List of posts sorted by drama score
    """
    if not posts:
        return []

    # Find max comments for normalization
    max_comments = max(post.get('comments', 0) for post in posts)

    # Compute scores and add as field
    for post in posts:
        post["drama_score"] = calculate_post_drama_score(post)

    # Sort posts by score in descending order
    ranked_posts = sorted(posts, key=lambda p: p["drama_score"], reverse=True)

    return ranked_posts


def fetch_post_comments(id):
    url = f"https://api.scored.co/api/v2/post/post.json?id={id}&comments=true&commentSort=controversial"
    response = requests.get(url)

    if response.status_code != 200:
        return None  # Handle failure case

    data = response.json()

    # Extract relevant fields
    post_info = {
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "score": data.get("score", 0),  # score_down score_up comments (num count)
        "comments": []
    }

    # Extract comments
    for comment in data.get("comments", []):
        post_info["comments"].append({
            "username": comment.get("author", "Unknown"),
            "score": comment.get("score", 0),
            "score_up": comment.get("score_up", 0),
            "score_down": comment.get("score_down", 0),
            "reply_count": len(comment.get("child_ids", [])),
            "id": comment.get("id", ""),
            "uuid": comment.get("uuid", ""),
            "comment_parent_id": comment.get("comment_parent_id", 0),
            "child_ids": comment.get("child_ids", []),
            "body": comment.get("content", ""),
            "date": comment.get("created", "")
        })
    # Replace parent and child ids with pointers to other comments
    comment_dict = {comment["id"]: comment for comment in post_info["comments"]}

    for comment in post_info["comments"]:
        parent_id = comment["comment_parent_id"]
        child_ids = comment["child_ids"]

        # Replace parent ID with actual reference if it exists
        comment["comment_parent"] = comment_dict.get(parent_id, None)

        # Replace child IDs with actual references
        comment["child_comments"] = [comment_dict[child_id] for child_id in child_ids if child_id in comment_dict]
    return post_info["comments"]


def rank_controversial_comments(comments):
    """

    :param comments: List of comment struct
    :return: List of comment struct sorted by comment drama score
    """
    if not comments:
        return []

    max_replies = max(c["reply_count"] for c in comments) if comments else 1

    def comment_score(comment):
        total_votes = comment["score_up"] + comment["score_down"]
        controversy = 1 - abs(
            (comment["score_up"] - comment["score_down"]) / (total_votes + 1)) if total_votes > 0 else 0
        engagement = math.log(1 + comment["reply_count"]) / math.log(1 + max_replies) if max_replies > 0 else 0
        return controversy * 0.5 + engagement * 0.5

    return sorted(comments, key=comment_score, reverse=True)


def add_drama_ranked_comments_to_posts(posts):
    """
    Fetches all comments from each post in posts, then sorts the comments by drama score

    :param posts: list of posts struct
    :return: list of posts struct with dramasort comments
    """
    updated_posts = []

    for post in posts:
        id = post["id"]
        comments = fetch_post_comments(id)
        ranked_comments = rank_controversial_comments(comments)

        updated_posts.append({**post, "comments": ranked_comments})

    return updated_posts


def numeric_score_to_string_descriptor(score):
    if score == 0:
        return "[ :1: :2: :3: :4: :5: ]"
    descriptor = "[ "
    if score < 0.2:
        descriptor += ":chudsmug: :2: :3: :4: :5:"
    elif score < 0.4:
        descriptor += ":doomerchud: " * 2 + " :3: :4: :5:"
    elif score < 0.6:
        descriptor += ":chudconcerned: " * 3 + " :4: :5:"
    elif score < 0.8:
        descriptor += ":chudseethe: " * 4 + ":5:"
    else:
        descriptor += ":chudrage: " * 5
    descriptor += "] "
    return descriptor

def get_singlepost_submission_title(post, title_truncate_len=497):
    title = numeric_score_to_string_descriptor(post["drama_score"])
    title += post["title"]
    return title[:title_truncate_len] + "..." if len(title) > title_truncate_len else title


def strip_html_tags(text):
    # Remove all HTML tags using regex
    return re.sub(r'<.*?>', '', text)


def strip_newlines(text):
    return text.replace("\n", " ")


def strip_text(text):
    text = strip_html_tags(text)
    text = strip_newlines(text)
    return text


def submission_comment_add(comment, text_truncate_len=400):
    text = ""
    comment_parent = comment["comment_parent"]
    if comment_parent:
        body = strip_text(comment_parent['body'])
        text += f"> {body[:text_truncate_len] + '...' if len(body) > text_truncate_len else body}"
        text += f" (+{comment_parent['score_up']}/-{comment_parent['score_down']})"
        text += "\n\n>"
    body = strip_text(comment['body'])
    text += f"> [{body[:text_truncate_len] + '...' if len(body) > text_truncate_len else body}"
    text += f"]({comment['permalink']})"
    text += f" (+{comment['score_up']}/-{comment['score_down']})"
    text += "\n\n<br>\n\n"
    return text


def get_post_body_summary(post, text_truncate_len=1000):
    text = ""
    if post['raw_content']:
        text = "> " + strip_text(post['raw_content'])
        text = text[:text_truncate_len] + "..." if len(text) > text_truncate_len else text
        text += "\n\n"
    return text


def get_finalized_post_urls(post):
    slug_url = get_slugified_url(post["salted_link"])
    post["link"] = slug_url
    linked_comments = post["comments"]
    for comment in linked_comments:
        comment["permalink"] = post['link'] + f"/{comment['uuid']}"
    post["comments"] = linked_comments  # idk about python copy stuff
    return post


def get_rdrama_submit_format_for_one_post(post):
    """
    Returns a submission struct with a title, link, and text body strings.
    :param post: Post struct to be formatted for rdrama submit
    :return: Submission struct with title, body & link for submit via api
    """
    submission = {"title": "", "body": "", "link": ""}
    include_comments = min(5, len(post["comments"]))
    submission["title"] = get_singlepost_submission_title(post)
    if not post["link"]:
        post = get_finalized_post_urls(post)
    submission['link'] = post['link'] + '?commentSort=controversial'
    submission["body"] = get_post_body_summary(post)
    submission['body'] += "#### Most Dramatic Comments \n\n"
    # TODO - don't include duplicate comments e.g. both parent and child separately, or multiple childs of same parent combine
    for i in range(0, include_comments):
        submission["body"] += submission_comment_add(post["comments"][i])
    submission["body"] += "---\n\n"
    submission[
        "body"] += ":marseysnappy: *'autodrama' for scored (thanks HeyMoon). Ping @GatanKot about bugs or " \
                   "ideas* :marseyagree:"
    return submission


def get_catalogue_title():
    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y-%m-%d")
    title = f"Scored.co Drama Report :chudrage: {formatted_date}"
    return title


def get_tabulated_catalogue_posts(posts, title_char_max_len=88):
    html_str = "<table>\n"
    table_headers = ["Score", "Post", "Community", "Votes", "Comments"]
    html_str += "<tr>\n"
    for header in table_headers:
        html_str += f"<th>{header}</th>\n"
    html_str += "</tr>"
    for post in posts:
        html_str += "<tr>"
        html_str += f"<td>{numeric_score_to_string_descriptor(post['drama_score'])}</td>\n"
        html_str += f"<td><a href={post['salted_link']}>" \
                    f"{post['title'][:title_char_max_len] + '...' if len(post['title']) > title_char_max_len else post['title']}" \
                    f"</a></td>\n"
        html_str += f"<td>{post['community']}</td>\n"
        html_str += f"<td>(+{post['score_up']}/-{post['score_down']})</td>\n"
        html_str += f"<td>{post['comments']}</td>\n"
        html_str += "</tr>\n"
    html_str += "</table>\n"
    return html_str


def get_rdrama_submit_format_for_catalogue(posts):
    submission = {"title": get_catalogue_title(), "body": "#### Top Drama\n", "link": ""}
    submission["body"] += get_tabulated_catalogue_posts(posts)
    submission["body"] += ":marseysnappy: *'autodrama' for scored (thanks HeyMoon). Ping @GatanKot about bugs or " \
                          "ideas* :marseyagree:"
    return submission
